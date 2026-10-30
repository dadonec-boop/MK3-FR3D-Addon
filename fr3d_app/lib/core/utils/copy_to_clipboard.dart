import 'copy_to_clipboard_io.dart'
    if (dart.library.html) 'copy_to_clipboard_web.dart' as impl;
import 'copy_to_clipboard_types.dart';

export 'copy_to_clipboard_types.dart';

/// Copies [text] to the clipboard. On insecure web (HTTP LAN) falls back to
/// `document.execCommand('copy')`, then to a `.txt` download.
Future<CopyToClipboardResult> copyToClipboard(String text) =>
    impl.copyToClipboard(text);
