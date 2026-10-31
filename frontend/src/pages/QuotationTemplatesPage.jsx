import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { LayoutTemplate, Plus } from 'lucide-react'
import { deleteTemplate, listTemplates } from '../api/quotations'
import { errorMessage } from '../api/subscriptions'
import { useConfirm, useToast } from '../components/Toast'
import { Empty, PageHeader, Skeleton, money } from '../components/ui'
import './Quotations.css'

export default function QuotationTemplatesPage() {
  const toast = useToast()
  const confirm = useConfirm()
  const [templates, setTemplates] = useState(null)
  const [error, setError] = useState('')

  const refresh = useCallback(() => {
    listTemplates()
      .then(setTemplates)
      .catch(() => setError('Could not load templates.'))
  }, [])

  useEffect(() => {
    refresh()
  }, [refresh])

  const remove = async (template) => {
    const ok = await confirm({
      title: `Delete "${template.name}"?`,
      message: 'Quotations already created from it are not affected.',
      confirmLabel: 'Delete template',
      tone: 'danger',
    })
    if (!ok) return
    try {
      await deleteTemplate(template.id)
      toast.success('Template deleted.')
      refresh()
    } catch (err) {
      toast.error(errorMessage(err))
    }
  }

  return (
    <div>
      <PageHeader
        eyebrow="Sales"
        title="Quotation templates"
        subtitle="Reusable plan and product lines, so a new offer takes seconds."
        actions={
          <>
            <Link className="btn-secondary" to="/quotations">
              Back to quotations
            </Link>
            <Link className="btn-primary" to="/quotation-templates/new">
              <Plus size={16} /> New template
            </Link>
          </>
        }
      />

      {error && <p className="form-error">{error}</p>}
      {!templates && !error && (
        <div className="template-grid">
          {[0, 1, 2].map((i) => (
            <Skeleton key={i} height={190} radius={14} />
          ))}
        </div>
      )}
      {templates && templates.length === 0 && (
        <Empty icon={LayoutTemplate} title="No templates yet">
          Save a plan with its usual product lines and reuse it on every new quotation.
        </Empty>
      )}
      {templates && templates.length > 0 && (
        <div className="template-grid">
          {templates.map((template) => (
            <article key={template.id} className="template-card">
              <div>
                <h2>{template.name}</h2>
                <p className="plan-ref">{template.plan_detail ? `Plan: ${template.plan_detail.name}` : 'No plan attached'}</p>
              </div>
              <ul className="template-items">
                {template.items.map((item) => (
                  <li key={item.id}>
                    <span>
                      {item.product_detail?.name} × {item.quantity}
                    </span>
                    <span>{money(item.unit_price * item.quantity, 2)}</span>
                  </li>
                ))}
              </ul>
              <div className="template-foot">
                <span>{template.items.length} line{template.items.length === 1 ? '' : 's'}</span>
                <button type="button" onClick={() => remove(template)}>
                  Delete
                </button>
              </div>
            </article>
          ))}
        </div>
      )}
    </div>
  )
}
