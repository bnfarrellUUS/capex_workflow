import { useEffect, useRef } from 'react'
import Quill from 'quill'
import 'quill/dist/quill.snow.css'

// Quill's default font/size formats are CSS classes, which email clients strip.
// Register the style-based attributors instead so those formats become inline
// styles that survive into the sent email.
const FONTS = ['Georgia', 'Tahoma', 'Times New Roman', 'Verdana']
const SIZES = ['12px', '18px', '24px']
/* eslint-disable @typescript-eslint/no-explicit-any */
const FontStyle: any = Quill.import('attributors/style/font')
FontStyle.whitelist = FONTS
Quill.register(FontStyle, true)
const SizeStyle: any = Quill.import('attributors/style/size')
SizeStyle.whitelist = SIZES
Quill.register(SizeStyle, true)
/* eslint-enable @typescript-eslint/no-explicit-any */

const TOOLBAR = [
  [{ font: [false, ...FONTS] }, { size: [false, ...SIZES] }],
  ['bold', 'italic', 'underline'],
  [{ color: [] }, { background: [] }],
  [{ list: 'ordered' }, { list: 'bullet' }],
  ['link'],
  ['clean'],
]

export function QuillEditor({
  value,
  onChange,
  onReady,
}: {
  value: string
  onChange: (html: string) => void
  onReady?: (insert: (text: string) => void) => void
}) {
  const elRef = useRef<HTMLDivElement>(null)
  const quillRef = useRef<Quill | null>(null)
  const onChangeRef = useRef(onChange)
  onChangeRef.current = onChange

  useEffect(() => {
    if (!elRef.current || quillRef.current) return
    const q = new Quill(elRef.current, { theme: 'snow', modules: { toolbar: TOOLBAR } })
    quillRef.current = q
    q.clipboard.dangerouslyPasteHTML(value)
    q.on('text-change', () => onChangeRef.current(q.root.innerHTML))
    onReady?.((text: string) => {
      const range = q.getSelection(true)
      q.insertText(range ? range.index : q.getLength(), text)
    })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // Sync external value only when it diverges (e.g. after Reset).
  useEffect(() => {
    const q = quillRef.current
    if (q && value !== q.root.innerHTML) q.clipboard.dangerouslyPasteHTML(value)
  }, [value])

  return <div className="bg-surface"><div ref={elRef} style={{ minHeight: 320 }} /></div>
}
