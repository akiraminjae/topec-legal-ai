/** Reflows PDF/OCR-extracted text for display.
 *
 * Extracted document text keeps the source PDF's hard line breaks (each line
 * wraps at the original print layout's width, often far narrower than our
 * screen). Rendered with `whitespace-pre-wrap`, those breaks show up as real
 * line breaks, so the paragraph never reflows to fill the available width —
 * it looks stuck in a narrow left-aligned column no matter how wide its
 * container is. This joins single line breaks within a paragraph into spaces
 * so the browser can reflow the text naturally, while still treating blank
 * lines as real paragraph breaks.
 */
export function dejustifyText(text: string | null | undefined): string {
  if (!text) return "";
  return text
    .replace(/\r\n/g, "\n")
    .split(/\n{2,}/)
    .map((paragraph) =>
      paragraph
        .split("\n")
        .map((line) => line.trim())
        .filter((line) => line.length > 0)
        .join(" ")
    )
    .join("\n\n");
}
