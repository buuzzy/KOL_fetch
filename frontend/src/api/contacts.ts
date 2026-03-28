import client from './client'

export interface Contact {
  id: string
  platform: string
  platform_id: string
  name: string
  email: string
  email_source: string
  follower_count: number
  profile_url: string
  content_focus: string
  contact_channels: Record<string, string[] | boolean>
  contact_status: string
  notes: string
  hk_relevance_score: number
  _channels: Record<string, string[] | boolean>
  _has_contact: boolean
  created_at: string
}

export interface ContactsData {
  contacts: Contact[]
  snapshots: { id: string; platform: string; total_kols: number; created_at: string }[]
  total: number
  with_email: number
  with_contact: number
}

export interface EmailTemplate {
  id: string
  name: string
  subject: string
  body: string
  created_by: string
  created_at: string
}

export interface ComposeData {
  templates: EmailTemplate[]
  contacts: Contact[]
}

export async function listContacts(): Promise<ContactsData> {
  const { data } = await client.get<ContactsData>('/api/contacts')
  return data
}

export async function importFromSnapshot(snapshotId: string) {
  const { data } = await client.post('/api/contacts/import', { snapshot_id: snapshotId })
  return data
}

export async function updateEmail(contactId: string, email: string) {
  await client.put(`/api/contacts/${contactId}/email`, { email })
}

export async function deleteContact(contactId: string) {
  await client.delete(`/api/contacts/${contactId}`)
}

export async function updateContactStatus(contactId: string, status: string) {
  await client.patch(`/api/contacts/${contactId}/status`, { status })
}

export async function batchDeleteContacts(ids: string[]) {
  await client.post('/api/contacts/batch-delete', { ids })
}

export async function listTemplates(): Promise<EmailTemplate[]> {
  const { data } = await client.get<EmailTemplate[]>('/api/contacts/templates')
  return data
}

export async function createTemplate(name: string, subject: string, bodyHtml: string) {
  const { data } = await client.post('/api/contacts/templates', { name, subject, body_html: bodyHtml })
  return data
}

export async function updateTemplate(id: string, updates: { name?: string; subject?: string; body_html?: string }) {
  await client.put(`/api/contacts/templates/${id}`, updates)
}

export async function deleteTemplate(id: string) {
  await client.delete(`/api/contacts/templates/${id}`)
}

export async function getComposeData(): Promise<ComposeData> {
  const { data } = await client.get<ComposeData>('/api/contacts/compose-data')
  return data
}

export async function sendEmails(templateId: string, contactIds: string[], fromName: string) {
  const { data } = await client.post('/api/contacts/send', {
    template_id: templateId,
    contact_ids: contactIds,
    from_name: fromName,
  })
  return data
}
