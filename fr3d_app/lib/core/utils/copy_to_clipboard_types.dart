/// Result of a copy attempt (web HTTP often cannot use Clipboard API).
enum CopyToClipboardResult {
  copied,
  downloaded,
  failed,
}
