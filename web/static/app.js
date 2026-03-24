/**
 * KOL 搜索中台 - 前端交互
 * SSE 实时进度 + 快照搜索过滤
 */

document.addEventListener('DOMContentLoaded', () => {
  initTaskProgress();
  initSnapshotSearch();
});

/* ── SSE 任务进度 ── */

function initTaskProgress() {
  const el = document.getElementById('task-app');
  if (!el) return;

  const taskId = el.dataset.taskId;
  const status = el.dataset.taskStatus;

  if (status === 'completed' || status === 'failed') return;

  const logLines = document.getElementById('log-lines');
  const logContainer = document.getElementById('log-container');
  const logCount = document.getElementById('log-count');
  const logCursor = document.getElementById('log-cursor');
  let count = 0;

  const evtSource = new EventSource(`/api/tasks/${taskId}/stream`);

  evtSource.onmessage = (event) => {
    const data = JSON.parse(event.data);

    if (data.type === 'log') {
      const line = document.createElement('div');
      line.className = 'py-0.5 border-b border-gray-800';
      line.textContent = data.message;
      logLines.appendChild(line);
      count++;
      logCount.textContent = `${count} 条`;
      logContainer.scrollTop = logContainer.scrollHeight;
    }

    if (data.type === 'done') {
      evtSource.close();
      logCursor.remove();

      const statusDot = document.getElementById('status-dot');
      const statusText = document.getElementById('status-text');

      if (data.status === 'completed') {
        statusDot.className = 'w-2.5 h-2.5 rounded-full mr-2 bg-green-500';
        statusText.textContent = '已完成';
        statusText.className = 'text-green-600 text-sm font-medium';

        if (data.summary) {
          const summaryCard = document.getElementById('summary-card');
          const summaryText = document.getElementById('summary-text');
          summaryCard.classList.remove('hidden');
          summaryText.textContent = `共发现 ${data.summary.total || 0} 个港澳财经 KOL`;
        }

        if (data.snapshot_id || data.report_paths) {
          const actions = document.getElementById('result-actions');
          actions.classList.remove('hidden');

          if (data.snapshot_id) {
            document.getElementById('btn-snapshot').href = `/snapshots/${data.snapshot_id}`;
          }
          if (data.report_paths && data.report_paths.xlsx) {
            const xlsxName = data.report_paths.xlsx.split('/').pop();
            document.getElementById('btn-xlsx').href = `/api/reports/download/${xlsxName}`;
          }
          if (data.report_paths && data.report_paths.csv) {
            const csvName = data.report_paths.csv.split('/').pop();
            document.getElementById('btn-csv').href = `/api/reports/download/${csvName}`;
          }
        }
      } else {
        statusDot.className = 'w-2.5 h-2.5 rounded-full mr-2 bg-red-500';
        statusText.textContent = '失败';
        statusText.className = 'text-red-600 text-sm font-medium';

        if (data.error) {
          const errorCard = document.getElementById('error-card');
          const errorText = document.getElementById('error-text');
          errorCard.classList.remove('hidden');
          errorText.textContent = data.error;
        }
      }
    }

    if (data.type === 'error') {
      evtSource.close();
      logCursor.remove();
      const line = document.createElement('div');
      line.className = 'py-0.5 text-red-400';
      line.textContent = data.message;
      logLines.appendChild(line);
    }
  };

  evtSource.onerror = () => {
    evtSource.close();
    if (logCursor) logCursor.remove();
  };
}

/* ── 快照 KOL 表格搜索过滤 ── */

function initSnapshotSearch() {
  const input = document.getElementById('kol-search');
  if (!input) return;

  input.addEventListener('input', () => {
    const query = input.value.toLowerCase();
    const rows = document.querySelectorAll('#kol-table tbody tr');
    rows.forEach(row => {
      const text = row.textContent.toLowerCase();
      row.style.display = text.includes(query) ? '' : 'none';
    });
  });
}

/* ── 表格列排序 ── */

let currentSortKey = null;
let currentSortAsc = true;

function sortTable(th) {
  const table = th.closest('table');
  if (!table) return;

  const key = th.dataset.sortKey;
  const type = th.dataset.sortType || 'string';

  if (currentSortKey === key) {
    currentSortAsc = !currentSortAsc;
  } else {
    currentSortKey = key;
    currentSortAsc = (type === 'number') ? false : true;
  }

  table.querySelectorAll('th .sort-arrow').forEach(el => {
    el.textContent = '';
    el.className = 'sort-arrow text-gray-300 ml-0.5';
  });
  const arrow = th.querySelector('.sort-arrow');
  if (arrow) {
    arrow.textContent = currentSortAsc ? '\u2191' : '\u2193';
    arrow.className = 'sort-arrow text-blue-600 ml-0.5';
  }

  const tbody = table.querySelector('tbody');
  const rows = Array.from(tbody.querySelectorAll('tr'));

  rows.sort((a, b) => {
    let va = a.dataset[key] || '';
    let vb = b.dataset[key] || '';
    if (type === 'number') {
      va = parseFloat(va) || 0;
      vb = parseFloat(vb) || 0;
      return currentSortAsc ? va - vb : vb - va;
    }
    return currentSortAsc ? va.localeCompare(vb, 'zh') : vb.localeCompare(va, 'zh');
  });

  rows.forEach((row, i) => {
    const idx = row.querySelector('.row-index');
    if (idx) idx.textContent = i + 1;
    tbody.appendChild(row);
  });
}
