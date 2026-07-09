import { api } from './client'

export interface Token { token: string; description: string }
export interface EmailTemplateSummary {
  type: string; name: string; subject: string; enabled: boolean; is_custom: boolean
}
export interface EmailTemplate extends EmailTemplateSummary {
  body_html: string
  default_subject: string
  default_body_html: string
  tokens: Token[]
  /** Label of the locked CTA button the email frame appends below the body. */
  button_label: string
}
export interface Preview { subject: string; html: string }

export function listEmailTemplates(): Promise<EmailTemplateSummary[]> {
  return api('/email-templates')
}
export function getEmailTemplate(type: string): Promise<EmailTemplate> {
  return api(`/email-templates/${type}`)
}
export function saveEmailTemplate(
  type: string, body: { subject: string; body_html: string; enabled: boolean },
): Promise<EmailTemplate> {
  return api(`/email-templates/${type}`, { method: 'PUT', body })
}
export function saveAsDefault(type: string): Promise<EmailTemplate> {
  return api(`/email-templates/${type}/save-as-default`, { method: 'POST' })
}
export function resetEmailTemplate(type: string): Promise<EmailTemplate> {
  return api(`/email-templates/${type}/reset`, { method: 'POST' })
}
export function previewEmailTemplate(
  type: string, body: { subject: string; body_html: string },
): Promise<Preview> {
  return api(`/email-templates/${type}/preview`, { method: 'POST', body })
}
