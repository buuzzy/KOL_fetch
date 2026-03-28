import toast from 'react-hot-toast'
import client from './client'

export async function downloadReport(filename: string) {
  try {
    const response = await client.get(`/api/reports/download/${filename}`, {
      responseType: 'blob',
    })
    const url = window.URL.createObjectURL(new Blob([response.data]))
    const a = document.createElement('a')
    a.href = url
    a.download = filename
    document.body.appendChild(a)
    a.click()
    a.remove()
    window.URL.revokeObjectURL(url)
  } catch {
    toast.error('报表下载失败，文件可能已过期或不存在')
  }
}
