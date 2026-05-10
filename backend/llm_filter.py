"""LLM 精筛模块：规则初筛后调用 LLM 做最终判断，生成结果摘要。

支持通过 criteria dict 动态配置筛选标准，前端可控。
"""

import json
import logging
from dataclasses import dataclass, field

import requests

from config import DEEPSEEK_API_KEY, LLM_BASE_URL, LLM_MODEL

logger = logging.getLogger(__name__)

# ── 前端可选项定义（前后端共享语义） ──

KOL_TYPE_OPTIONS = [
    {"id": "stock_analysis", "label": "股票/证券分析"},
    {"id": "wealth_mgmt", "label": "理财规划/财务自由"},
    {"id": "crypto", "label": "加密货币/Web3"},
    {"id": "macro", "label": "宏观经济评论"},
    {"id": "edu", "label": "投资教学/课程"},
    {"id": "derivatives", "label": "期权/衍生品"},
]

EXCLUDE_TYPE_OPTIONS = [
    {"id": "media", "label": "媒体/新闻机构"},
    {"id": "institution", "label": "券商/银行/基金公司"},
    {"id": "insurance", "label": "保险顾问/理财经纪"},
    {"id": "realestate", "label": "房产中介"},
]

AUDIENCE_OPTIONS = [
    {"id": "hk_macau", "label": "港澳地区"},
    {"id": "greater_china", "label": "大中华区（含台湾）"},
    {"id": "global_chinese", "label": "全球华人"},
]

DEFAULT_CRITERIA = {
    "kol_types": [],
    "exclude_types": ["media", "institution", "insurance", "realestate"],
    "audience": "hk_macau",
    "custom_requirements": "",
}


def _build_system_prompt(criteria: dict | None = None) -> str:
    """根据 criteria 动态构建 system prompt。"""
    c = {**DEFAULT_CRITERIA, **(criteria or {})}

    type_label_map = {o["id"]: o["label"] for o in KOL_TYPE_OPTIONS}
    exclude_label_map = {o["id"]: o["label"] for o in EXCLUDE_TYPE_OPTIONS}
    audience_label_map = {o["id"]: o["label"] for o in AUDIENCE_OPTIONS}

    selected_types = [type_label_map[t] for t in c.get("kol_types", []) if t in type_label_map]
    if selected_types:
        type_desc = "、".join(selected_types)
        finance_criterion = f"内容主要围绕以下领域：{type_desc}"
    else:
        finance_criterion = "内容主要围绕投资、理财、股票、基金、加密货币等财经主题"

    excluded = [exclude_label_map[e] for e in c.get("exclude_types", []) if e in exclude_label_map]
    if excluded:
        exclude_desc = "、".join(excluded)
        identity_criterion = f"必须是个人博主，排除以下类型：{exclude_desc}"
    else:
        identity_criterion = "必须是个人博主（但不限制机构类型）"

    audience_id = c.get("audience", "hk_macau")
    audience_label = audience_label_map.get(audience_id, "港澳地区")
    audience_criterion = f"内容面向「{audience_label}」的受众"

    custom = c.get("custom_requirements", "").strip()
    custom_section = ""
    if custom:
        custom_section = f"""
## MKT 补充要求

{custom}
"""

    return f"""\
你是一位专业的社交媒体 KOL 筛选助手，服务于一家香港金融公司的市场部（MKT）。

MKT 的需求是：找到符合条件的个人博主（KOL），用于后续商务合作。

## 判断标准（必须同时满足）

1. **身份要求**：{identity_criterion}
2. **内容方向**：{finance_criterion}
3. **目标受众**：{audience_criterion}

## 常见误判案例

- 名称含"港股"但实际是舞蹈团/娱乐账号 → reject
- 个人简介提到投资但实际是保险销售/房产中介 → 需根据内容综合判断
- 频道/账号同时覆盖多个地区 → 如果有明显目标受众内容则 pass
- 财经媒体（如彭博、信報、經濟日報） → 根据排除设置判断
- 大型机构（如富途、老虎証券、匯豐） → 根据排除设置判断
{custom_section}
## 输出格式

严格输出 JSON 数组，每个元素包含：
- id: 候选人的唯一标识（原样返回）
- verdict: "pass" 或 "reject"
- reason: 一句话判断理由（中文，15字以内）
- confidence: 0.0~1.0 的置信度

示例：
[
  {{"id": "UC1234", "verdict": "pass", "reason": "港股技術分析個人博主", "confidence": 0.95}},
  {{"id": "UC5678", "verdict": "reject", "reason": "舞蹈團非財經賬號", "confidence": 0.99}}
]

只输出 JSON，不要附加任何解释文字。"""


SUMMARY_PROMPT = """\
你是社交媒体 KOL 发现系统的分析助手。

MKT 团队发起了一次 KOL 搜索，以下是搜索结果概况：

- 平台: {platform}
- 搜索关键词: {keywords}
- 粉丝范围: {min_followers:,} ~ {max_followers:,}
- 博主类型偏好: {kol_types_desc}
- 目标受众: {audience_desc}
- 规则筛选后候选人: {rule_passed} 个
- LLM 精筛通过: {llm_passed} 个
- 最终入选 KOL: {final_count} 个

{shortfall_note}

请用 2~3 句话生成一段面向 MKT 同事的中文分析摘要，包含：
1. 搜索范围和结果概述
2. 如果结果不足，分析可能原因并给出调整建议（如扩大关键词、放宽粉丝范围、增加平台等）
3. 如果结果充足，简要总结 KOL 的特征分布

语气专业但简洁，不要用 markdown 格式。"""


@dataclass
class FilterResult:
    passed: list[dict] = field(default_factory=list)
    rejected: list[dict] = field(default_factory=list)
    summary: str = ""
    llm_token_usage: int = 0


def _call_llm(messages: list[dict], max_tokens: int = 2000) -> dict:
    if not DEEPSEEK_API_KEY:
        raise RuntimeError("DEEPSEEK_API_KEY 未配置")

    url = f"{LLM_BASE_URL}/chat/completions"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
    }
    payload = {
        "model": LLM_MODEL,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": 0.1,
    }

    resp = requests.post(url, headers=headers, json=payload, timeout=120)
    resp.raise_for_status()
    return resp.json()


def _build_candidate_text(candidates: list[dict]) -> str:
    lines = []
    for c in candidates:
        parts = [
            f"ID: {c['id']}",
            f"名称: {c['name']}",
            f"粉丝: {c['followers']:,}",
        ]
        if c.get("category"):
            parts.append(f"分类: {c['category']}")
        if c.get("bio"):
            bio = c["bio"][:200].replace("\n", " ")
            parts.append(f"简介: {bio}")
        if c.get("recent_titles"):
            titles = " | ".join(c["recent_titles"][:3])
            parts.append(f"近期内容: {titles}")
        if c.get("tags"):
            parts.append(f"标签: {', '.join(c['tags'][:5])}")

        lines.append(" | ".join(parts))
    return "\n".join(lines)


def _normalize_candidates(kols: list, platform: str) -> list[dict]:
    result = []
    for k in kols:
        d = k.to_dict() if hasattr(k, "to_dict") else dict(k)
        recent_titles = d.get("recent_titles", [])
        if not recent_titles and d.get("recent_posts"):
            recent_titles = [p for p in d["recent_posts"] if p]

        normalized = {
            "id": d.get("channel_id") or d.get("username", ""),
            "name": d.get("name", ""),
            "followers": d.get("subscriber_count") or d.get("follower_count", 0),
            "bio": d.get("description") or d.get("biography", ""),
            "category": d.get("category", ""),
            "recent_titles": recent_titles,
            "tags": d.get("content_focus", []),
            "platform": platform,
            "_original": k,
        }
        result.append(normalized)
    return result


def llm_filter_candidates(
    kols: list,
    platform: str,
    criteria: dict | None = None,
    batch_size: int = 25,
) -> FilterResult:
    """对候选 KOL 做 LLM 精筛。

    criteria: 前端传入的筛选条件，用于动态构建 prompt
    """
    if not kols:
        return FilterResult()

    if not DEEPSEEK_API_KEY:
        logger.warning("[LLM] 未配置 API，跳过精筛，全部保留")
        return FilterResult(
            passed=[{"_original": k} for k in kols],
            summary="DEEPSEEK_API_KEY 未配置，已跳过精筛环节。",
        )

    system_prompt = _build_system_prompt(criteria)
    candidates = _normalize_candidates(kols, platform)
    all_verdicts: dict[str, dict] = {}
    total_tokens = 0

    for i in range(0, len(candidates), batch_size):
        batch = candidates[i: i + batch_size]
        batch_num = i // batch_size + 1
        total_batches = (len(candidates) + batch_size - 1) // batch_size
        logger.info(
            f"[LLM] 精筛批次 {batch_num}/{total_batches}，"
            f"本批 {len(batch)} 个候选人"
        )

        candidate_text = _build_candidate_text(batch)
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"以下是 {len(batch)} 个候选 KOL，请逐一判断：\n\n{candidate_text}"},
        ]

        try:
            resp = _call_llm(messages, max_tokens=len(batch) * 80)
            content = resp["choices"][0]["message"]["content"].strip()
            usage = resp.get("usage", {})
            total_tokens += usage.get("total_tokens", 0)

            if content.startswith("```"):
                content = content.split("\n", 1)[-1].rsplit("```", 1)[0]

            verdicts = json.loads(content)
            for v in verdicts:
                all_verdicts[v["id"]] = v
                logger.info(
                    f"[LLM]   {v['id']}: {v['verdict']} — {v.get('reason', '')}"
                )
        except json.JSONDecodeError as e:
            logger.error(f"[LLM] JSON 解析失败: {e}，本批全部保留")
            for c in batch:
                all_verdicts[c["id"]] = {
                    "id": c["id"], "verdict": "pass",
                    "reason": "LLM 响应解析失败，默认保留", "confidence": 0.0,
                }
        except Exception as e:
            logger.error(f"[LLM] 调用失败: {e}，本批全部保留")
            for c in batch:
                all_verdicts[c["id"]] = {
                    "id": c["id"], "verdict": "pass",
                    "reason": "LLM 调用失败，默认保留", "confidence": 0.0,
                }

    passed = []
    rejected = []
    for c in candidates:
        verdict = all_verdicts.get(c["id"], {})
        original = c["_original"]
        v = verdict.get("verdict", "pass")

        if hasattr(original, "llm_verdict"):
            original.llm_verdict = v
            original.llm_reason = verdict.get("reason", "")

        entry = {
            "_original": original,
            "verdict": v,
            "reason": verdict.get("reason", ""),
            "confidence": verdict.get("confidence", 0.0),
        }
        if v == "pass":
            passed.append(entry)
        else:
            rejected.append(entry)

    logger.info(
        f"[LLM] 精筛完成: {len(passed)} 通过, "
        f"{len(rejected)} 淘汰, token 用量 {total_tokens}"
    )
    return FilterResult(
        passed=passed,
        rejected=rejected,
        llm_token_usage=total_tokens,
    )


def generate_summary(
    result: FilterResult,
    platform: str,
    keywords: list[str],
    min_followers: int,
    max_followers: int,
    rule_passed_count: int,
    criteria: dict | None = None,
    target_count: int | None = None,
) -> str:
    c = criteria or DEFAULT_CRITERIA
    final_count = len(result.passed)

    type_label_map = {o["id"]: o["label"] for o in KOL_TYPE_OPTIONS}
    audience_label_map = {o["id"]: o["label"] for o in AUDIENCE_OPTIONS}
    kol_types_desc = "、".join(
        type_label_map[t] for t in c.get("kol_types", []) if t in type_label_map
    ) or "泛财经"
    audience_desc = audience_label_map.get(c.get("audience", "hk_macau"), "港澳地区")

    if target_count and final_count >= target_count:
        return (
            f"本次搜索覆盖 {len(keywords)} 个关键词（{kol_types_desc}方向），"
            f"规则筛选通过 {rule_passed_count} 个候选人，"
            f"经 AI 精筛后最终入选 {final_count} 个面向{audience_desc}的 KOL。"
        )

    shortfall_note = ""
    if target_count:
        shortfall_note = (
            f"MKT 期望找到 {target_count} 个 KOL，"
            f"但最终只有 {final_count} 个通过精筛，缺口 {target_count - final_count} 个。"
        )

    if not DEEPSEEK_API_KEY:
        if shortfall_note:
            return (
                f"本次搜索最终入选 {final_count} 个 KOL。{shortfall_note}"
                f"建议扩大搜索关键词或放宽粉丝范围。"
            )
        return (
            f"本次搜索覆盖 {len(keywords)} 个关键词，"
            f"最终入选 {final_count} 个面向{audience_desc}的 KOL。"
        )

    prompt = SUMMARY_PROMPT.format(
        platform=platform,
        keywords="、".join(keywords[:10]),
        min_followers=min_followers,
        max_followers=max_followers,
        kol_types_desc=kol_types_desc,
        audience_desc=audience_desc,
        rule_passed=rule_passed_count,
        llm_passed=final_count,
        final_count=final_count,
        shortfall_note=shortfall_note,
    )

    try:
        resp = _call_llm(
            [{"role": "user", "content": prompt}],
            max_tokens=300,
        )
        return resp["choices"][0]["message"]["content"].strip()
    except Exception as e:
        logger.error(f"[LLM] 摘要生成失败: {e}")
        fallback = (
            f"本次搜索覆盖 {len(keywords)} 个关键词，"
            f"最终入选 {final_count} 个面向{audience_desc}的 KOL。"
        )
        if shortfall_note:
            fallback += shortfall_note
        return fallback
