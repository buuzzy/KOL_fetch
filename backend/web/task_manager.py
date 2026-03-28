"""后台任务调度：ThreadPoolExecutor 运行长时间 KOL 发现任务，捕获日志输出为 SSE 进度流。"""

import asyncio
import json
import logging
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime, timezone

from web.deps import get_admin_client


@dataclass
class TaskState:
    task_id: str
    task_type: str  # "youtube" | "instagram"
    status: str = "pending"  # pending / running / completed / failed
    logs: list[str] = field(default_factory=list)
    report_paths: dict = field(default_factory=dict)
    result_summary: dict = field(default_factory=dict)
    error: str = ""
    created_at: float = field(default_factory=time.time)


class _TaskLogHandler(logging.Handler):
    """拦截现有模块的 logger.info() 输出，写入 TaskState.logs。"""

    def __init__(self, task_state: TaskState):
        super().__init__()
        self._state = task_state

    def emit(self, record: logging.LogRecord):
        try:
            msg = self.format(record)
            self._state.logs.append(msg)
        except Exception:
            pass


class TaskManager:
    _YOUTUBE_LOGGERS = ["discovery", "youtube_client", "llm_filter"]
    _IG_LOGGERS = ["instagram_discovery", "instagram_client", "llm_filter"]
    _THREADS_LOGGERS = ["threads_discovery", "threads_client", "llm_filter"]

    def __init__(self, max_workers: int = 2):
        self._executor = ThreadPoolExecutor(max_workers=max_workers)
        self._tasks: dict[str, TaskState] = {}

    def shutdown(self):
        self._executor.shutdown(wait=False)

    def get_state(self, task_id: str) -> TaskState | None:
        return self._tasks.get(task_id)

    def list_tasks(self) -> list[TaskState]:
        return sorted(self._tasks.values(), key=lambda t: t.created_at, reverse=True)

    # ── YouTube 任务 ──

    def submit_youtube(self, params: dict, user_id: str) -> str:
        task_id = str(uuid.uuid4())
        state = TaskState(task_id=task_id, task_type="youtube", status="pending")
        self._tasks[task_id] = state
        self._save_to_db(state, user_id, params)
        self._executor.submit(self._run_youtube, state, params, user_id)
        return task_id

    def _run_youtube(self, state: TaskState, params: dict, user_id: str):
        handler = _TaskLogHandler(state)
        handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", datefmt="%H:%M:%S"))
        loggers = [logging.getLogger(n) for n in self._YOUTUBE_LOGGERS]
        saved_levels = {}
        for lg in loggers:
            saved_levels[lg.name] = lg.level
            lg.setLevel(logging.DEBUG)
            lg.addHandler(handler)

        state.status = "running"
        self._update_db_status(state.task_id, "running")

        try:
            from youtube_client import YouTubeClient, QuotaExhaustedError
            from discovery import discover_kols
            from report import export_csv, export_excel

            strategy = params.get("strategy", "video")
            max_pages = int(params.get("pages", 3))
            min_subs = int(params.get("min_subscribers", 1000))
            max_subs = int(params.get("max_subscribers", 200000))

            selected_kw = params.get("selected_keywords", "")
            custom_kw = params.get("custom_keywords", "")
            keywords = [k.strip() for k in selected_kw.strip().splitlines() if k.strip()]
            if custom_kw.strip():
                keywords += [k.strip() for k in custom_kw.strip().splitlines() if k.strip()]
            keywords = list(dict.fromkeys(keywords))

            if not keywords:
                from config import SEARCH_KEYWORDS
                keywords = SEARCH_KEYWORDS

            max_inactive_days = int(params.get("max_inactive_days", 90))

            depth_label = {"fast": "快速扫描", "standard": "标准搜索", "deep": "深度搜索"}
            inactive_label = f"{max_inactive_days} 天内活跃" if max_inactive_days > 0 else "不限"
            state.logs.append(
                f"关键词: {len(keywords)} 个 | 模式: {depth_label.get(params.get('depth', ''), '标准')} | "
                f"订阅范围: {min_subs:,} ~ {max_subs:,} | 活跃度: {inactive_label}"
            )

            from llm_filter import llm_filter_candidates, generate_summary

            client = YouTubeClient()
            state.logs.append(f"已加载 {len(client._api_keys)} 个 API Key")
            try:
                kols = discover_kols(
                    client=client, keywords=keywords,
                    min_subscribers=min_subs, max_subscribers=max_subs,
                    max_pages=max_pages, strategy=strategy,
                    max_inactive_days=max_inactive_days,
                )
            except QuotaExhaustedError as e:
                state.logs.append(f"Quota 耗尽: {e}")
                kols = []

            if not kols:
                state.logs.append("未找到符合条件的 KOL")
                state.status = "completed"
                state.result_summary = {"total": 0, "quota_used": client.quota_used}
                self._update_db_finish(state.task_id, "completed", state.result_summary)
                return

            rule_passed_count = len(kols)

            llm_criteria = params.get("llm_criteria")
            summary_text = ""

            if llm_criteria is not None:
                state.logs.append(f"规则筛选通过 {rule_passed_count} 个，进入 AI 精筛...")
                filter_result = llm_filter_candidates(kols, "youtube", criteria=llm_criteria)
                kols = [entry["_original"] for entry in filter_result.passed]

                summary_text = generate_summary(
                    filter_result, "YouTube", keywords,
                    min_subs, max_subs, rule_passed_count,
                    criteria=llm_criteria,
                )
                filter_result.summary = summary_text
                state.logs.append(f"AI 精筛完成: {len(kols)}/{rule_passed_count} 通过")

                if not kols:
                    state.logs.append("AI 精筛后无符合条件的 KOL")
                    state.status = "completed"
                    state.result_summary = {
                        "total": 0, "quota_used": client.quota_used,
                        "rule_passed": rule_passed_count,
                        "llm_summary": summary_text,
                    }
                    self._update_db_finish(state.task_id, "completed", state.result_summary)
                    return
            else:
                state.logs.append(f"规则筛选通过 {rule_passed_count} 个（AI 精筛已关闭）")

            csv_path = export_csv(kols)
            xlsx_path = export_excel(kols)

            kols_data = [k.to_dict() for k in kols]
            snapshot_id = self._save_snapshot_to_db(
                kols_data, "youtube", params, user_id,
            )

            state.report_paths = {"csv": csv_path, "xlsx": xlsx_path}
            result_summary: dict = {
                "total": len(kols),
                "quota_used": client.quota_used,
                "rule_passed": rule_passed_count,
                "snapshot_id": snapshot_id,
                "top3": [{"name": k.name, "subscribers": k.subscriber_count} for k in kols[:3]],
            }
            if llm_criteria is not None:
                result_summary["llm_passed"] = len(kols)
                result_summary["llm_rejected"] = len(filter_result.rejected)
                result_summary["llm_summary"] = summary_text
            state.result_summary = result_summary
            state.status = "completed"

            if llm_criteria is not None:
                state.logs.append(
                    f"完成! 发现 {len(kols)} 个 KOL "
                    f"(规则 {rule_passed_count} → AI {len(kols)}), "
                    f"Quota 已用 {client.quota_used}"
                )
            else:
                state.logs.append(
                    f"完成! 发现 {len(kols)} 个 KOL "
                    f"(规则筛选 {rule_passed_count} 个), "
                    f"Quota 已用 {client.quota_used}"
                )
            self._update_db_finish(state.task_id, "completed", state.result_summary)

        except Exception as e:
            state.status = "failed"
            state.error = str(e)
            state.logs.append(f"任务失败: {e}")
            self._update_db_finish(state.task_id, "failed", error=str(e))

        finally:
            for lg in loggers:
                lg.removeHandler(handler)
                lg.setLevel(saved_levels.get(lg.name, logging.NOTSET))

    # ── Instagram 任务 ──

    def submit_instagram(self, params: dict, user_id: str) -> str:
        task_id = str(uuid.uuid4())
        state = TaskState(task_id=task_id, task_type="instagram", status="pending")
        self._tasks[task_id] = state
        self._save_to_db(state, user_id, params)
        self._executor.submit(self._run_instagram, state, params, user_id)
        return task_id

    def _run_instagram(self, state: TaskState, params: dict, user_id: str):
        handler = _TaskLogHandler(state)
        handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", datefmt="%H:%M:%S"))
        loggers = [logging.getLogger(n) for n in self._IG_LOGGERS]
        saved_levels = {}
        for lg in loggers:
            saved_levels[lg.name] = lg.level
            lg.setLevel(logging.DEBUG)
            lg.addHandler(handler)

        state.status = "running"
        self._update_db_status(state.task_id, "running")

        try:
            from instagram_client import InstagramClient
            from instagram_discovery import discover_ig_kols
            from report import export_ig_csv, export_ig_excel

            min_followers = int(params.get("min_followers", 1000))
            max_followers = int(params.get("max_followers", 200000))

            selected_kw = params.get("selected_keywords", "")
            custom_kw = params.get("custom_keywords", "")
            keywords = [k.strip() for k in selected_kw.strip().splitlines() if k.strip()]
            if custom_kw.strip():
                keywords += [k.strip() for k in custom_kw.strip().splitlines() if k.strip()]
            keywords = list(dict.fromkeys(keywords))

            if not keywords:
                from config import IG_SEARCH_KEYWORDS
                keywords = IG_SEARCH_KEYWORDS

            from llm_filter import llm_filter_candidates, generate_summary

            state.logs.append(f"[IG] 关键词: {len(keywords)} 个 | 粉丝范围: {min_followers:,} ~ {max_followers:,}")

            client = InstagramClient()
            kols = discover_ig_kols(
                client=client, keywords=keywords,
                min_followers=min_followers, max_followers=max_followers,
            )

            if not kols:
                state.logs.append("[IG] 未找到符合条件的 KOL")
                state.status = "completed"
                state.result_summary = {"total": 0, "api_calls": client.request_count, "cost": client.estimated_cost}
                self._update_db_finish(state.task_id, "completed", state.result_summary)
                return

            rule_passed_count = len(kols)

            llm_criteria = params.get("llm_criteria")
            summary_text = ""

            if llm_criteria is not None:
                state.logs.append(f"[IG] 规则筛选通过 {rule_passed_count} 个，进入 AI 精筛...")
                filter_result = llm_filter_candidates(kols, "instagram", criteria=llm_criteria)
                kols = [entry["_original"] for entry in filter_result.passed]

                summary_text = generate_summary(
                    filter_result, "Instagram", keywords,
                    min_followers, max_followers, rule_passed_count,
                    criteria=llm_criteria,
                )
                filter_result.summary = summary_text
                state.logs.append(f"[IG] AI 精筛完成: {len(kols)}/{rule_passed_count} 通过")

                if not kols:
                    state.logs.append("[IG] AI 精筛后无符合条件的 KOL")
                    state.status = "completed"
                    state.result_summary = {
                        "total": 0, "api_calls": client.request_count,
                        "cost": round(client.estimated_cost, 3),
                        "rule_passed": rule_passed_count,
                        "llm_summary": summary_text,
                    }
                    self._update_db_finish(state.task_id, "completed", state.result_summary)
                    return
            else:
                state.logs.append(f"[IG] 规则筛选通过 {rule_passed_count} 个（AI 精筛已关闭）")

            csv_path = export_ig_csv(kols)
            xlsx_path = export_ig_excel(kols)

            kols_data = [k.to_dict() for k in kols]
            snapshot_id = self._save_snapshot_to_db(
                kols_data, "instagram", params, user_id,
            )

            state.report_paths = {"csv": csv_path, "xlsx": xlsx_path}
            ig_summary: dict = {
                "total": len(kols),
                "api_calls": client.request_count,
                "cost": round(client.estimated_cost, 3),
                "rule_passed": rule_passed_count,
                "snapshot_id": snapshot_id,
                "top3": [{"name": k.name, "followers": k.follower_count} for k in kols[:3]],
            }
            if llm_criteria is not None:
                ig_summary["llm_passed"] = len(kols)
                ig_summary["llm_rejected"] = len(filter_result.rejected)
                ig_summary["llm_summary"] = summary_text
            state.result_summary = ig_summary
            state.status = "completed"

            if llm_criteria is not None:
                state.logs.append(
                    f"[IG] 完成! 发现 {len(kols)} 个 KOL "
                    f"(规则 {rule_passed_count} → AI {len(kols)}), "
                    f"费用 ${client.estimated_cost:.3f}"
                )
            else:
                state.logs.append(
                    f"[IG] 完成! 发现 {len(kols)} 个 KOL "
                    f"(规则筛选 {rule_passed_count} 个), "
                    f"费用 ${client.estimated_cost:.3f}"
                )
            self._update_db_finish(state.task_id, "completed", state.result_summary)

        except Exception as e:
            state.status = "failed"
            state.error = str(e)
            state.logs.append(f"[IG] 任务失败: {e}")
            self._update_db_finish(state.task_id, "failed", error=str(e))

        finally:
            for lg in loggers:
                lg.removeHandler(handler)
                lg.setLevel(saved_levels.get(lg.name, logging.NOTSET))

    # ── Threads 任务 ──

    def submit_threads(self, params: dict, user_id: str) -> str:
        task_id = str(uuid.uuid4())
        state = TaskState(task_id=task_id, task_type="threads", status="pending")
        self._tasks[task_id] = state
        self._save_to_db(state, user_id, params)
        self._executor.submit(self._run_threads, state, params, user_id)
        return task_id

    def _run_threads(self, state: TaskState, params: dict, user_id: str):
        handler = _TaskLogHandler(state)
        handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", datefmt="%H:%M:%S"))
        loggers = [logging.getLogger(n) for n in self._THREADS_LOGGERS]
        saved_levels = {}
        for lg in loggers:
            saved_levels[lg.name] = lg.level
            lg.setLevel(logging.DEBUG)
            lg.addHandler(handler)

        state.status = "running"
        self._update_db_status(state.task_id, "running")

        try:
            from threads_client import ThreadsClient
            from threads_discovery import discover_threads_kols
            from report import export_threads_csv, export_threads_excel

            min_followers = int(params.get("min_followers", 500))
            max_followers = int(params.get("max_followers", 500000))

            selected_kw = params.get("selected_keywords", "")
            custom_kw = params.get("custom_keywords", "")
            keywords = [k.strip() for k in selected_kw.strip().splitlines() if k.strip()]
            if custom_kw.strip():
                keywords += [k.strip() for k in custom_kw.strip().splitlines() if k.strip()]
            keywords = list(dict.fromkeys(keywords))

            if not keywords:
                from config import THREADS_SEARCH_KEYWORDS
                keywords = THREADS_SEARCH_KEYWORDS

            from llm_filter import llm_filter_candidates, generate_summary

            state.logs.append(
                f"[Threads] 关键词: {len(keywords)} 个 | 粉丝范围: {min_followers:,} ~ {max_followers:,}"
            )

            client = ThreadsClient()
            kols = discover_threads_kols(
                client=client, keywords=keywords,
                min_followers=min_followers, max_followers=max_followers,
            )

            if not kols:
                state.logs.append("[Threads] 未找到符合条件的 KOL")
                state.status = "completed"
                state.result_summary = {
                    "total": 0, "api_calls": client.request_count,
                    "cost": round(client.estimated_cost, 3),
                }
                self._update_db_finish(state.task_id, "completed", state.result_summary)
                return

            rule_passed_count = len(kols)

            llm_criteria = params.get("llm_criteria")
            summary_text = ""

            if llm_criteria is not None:
                state.logs.append(f"[Threads] 规则筛选通过 {rule_passed_count} 个，进入 AI 精筛...")
                filter_result = llm_filter_candidates(kols, "threads", criteria=llm_criteria)
                kols = [entry["_original"] for entry in filter_result.passed]

                summary_text = generate_summary(
                    filter_result, "Threads", keywords,
                    min_followers, max_followers, rule_passed_count,
                    criteria=llm_criteria,
                )
                filter_result.summary = summary_text
                state.logs.append(f"[Threads] AI 精筛完成: {len(kols)}/{rule_passed_count} 通过")

                if not kols:
                    state.logs.append("[Threads] AI 精筛后无符合条件的 KOL")
                    state.status = "completed"
                    state.result_summary = {
                        "total": 0, "api_calls": client.request_count,
                        "cost": round(client.estimated_cost, 3),
                        "rule_passed": rule_passed_count,
                        "llm_summary": summary_text,
                    }
                    self._update_db_finish(state.task_id, "completed", state.result_summary)
                    return
            else:
                state.logs.append(f"[Threads] 规则筛选通过 {rule_passed_count} 个（AI 精筛已关闭）")

            csv_path = export_threads_csv(kols)
            xlsx_path = export_threads_excel(kols)

            kols_data = [k.to_dict() for k in kols]
            snapshot_id = self._save_snapshot_to_db(
                kols_data, "threads", params, user_id,
            )

            state.report_paths = {"csv": csv_path, "xlsx": xlsx_path}
            threads_summary: dict = {
                "total": len(kols),
                "api_calls": client.request_count,
                "cost": round(client.estimated_cost, 3),
                "rule_passed": rule_passed_count,
                "snapshot_id": snapshot_id,
                "top3": [{"name": k.name, "followers": k.follower_count} for k in kols[:3]],
            }
            if llm_criteria is not None:
                threads_summary["llm_passed"] = len(kols)
                threads_summary["llm_rejected"] = len(filter_result.rejected)
                threads_summary["llm_summary"] = summary_text
            state.result_summary = threads_summary
            state.status = "completed"

            if llm_criteria is not None:
                state.logs.append(
                    f"[Threads] 完成! 发现 {len(kols)} 个 KOL "
                    f"(规则 {rule_passed_count} → AI {len(kols)}), "
                    f"费用 ${client.estimated_cost:.3f}"
                )
            else:
                state.logs.append(
                    f"[Threads] 完成! 发现 {len(kols)} 个 KOL "
                    f"(规则筛选 {rule_passed_count} 个), "
                    f"费用 ${client.estimated_cost:.3f}"
                )
            self._update_db_finish(state.task_id, "completed", state.result_summary)

        except Exception as e:
            state.status = "failed"
            state.error = str(e)
            state.logs.append(f"[Threads] 任务失败: {e}")
            self._update_db_finish(state.task_id, "failed", error=str(e))

        finally:
            for lg in loggers:
                lg.removeHandler(handler)
                lg.setLevel(saved_levels.get(lg.name, logging.NOTSET))

    # ── SSE 进度流 ──

    async def stream_progress(self, task_id: str):
        """异步生成器，以 SSE 格式推送任务进度日志。"""
        state = self._tasks.get(task_id)
        if not state:
            yield f"data: {json.dumps({'type': 'error', 'message': '任务不存在'})}\n\n"
            return

        idx = 0
        while True:
            while idx < len(state.logs):
                yield f"data: {json.dumps({'type': 'log', 'message': state.logs[idx]}, ensure_ascii=False)}\n\n"
                idx += 1

            if state.status in ("completed", "failed"):
                payload = {
                    "type": "done",
                    "status": state.status,
                    "summary": state.result_summary,
                    "snapshot_id": state.result_summary.get("snapshot_id", ""),
                    "report_paths": state.report_paths,
                    "error": state.error,
                }
                yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"
                return

            await asyncio.sleep(0.5)

    # ── Supabase 快照存储 ──

    @staticmethod
    def _save_snapshot_to_db(kols_data: list[dict], platform: str,
                             params: dict, user_id: str) -> str | None:
        try:
            from storage import save_snapshot_db
            return save_snapshot_db(kols_data, platform, params, user_id)
        except Exception:
            return None

    # ── Supabase DB 持久化 ──

    def _save_to_db(self, state: TaskState, user_id: str, params: dict):
        try:
            client = get_admin_client()
            client.table("tasks").insert({
                "id": state.task_id,
                "task_type": state.task_type,
                "status": state.status,
                "params": params,
                "created_by": user_id,
            }).execute()
        except Exception:
            pass

    def _update_db_status(self, task_id: str, status: str):
        try:
            client = get_admin_client()
            client.table("tasks").update({"status": status}).eq("id", task_id).execute()
        except Exception:
            pass

    def _update_db_finish(self, task_id: str, status: str, summary: dict | None = None,
                          error: str = ""):
        try:
            client = get_admin_client()
            update = {
                "status": status,
                "finished_at": datetime.now(timezone.utc).isoformat(),
            }
            if summary:
                update["result_summary"] = summary
            if error:
                update["error_message"] = error
            client.table("tasks").update(update).eq("id", task_id).execute()
        except Exception:
            pass


task_manager = TaskManager()
