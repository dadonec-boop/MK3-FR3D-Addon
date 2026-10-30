import 'package:flutter/services.dart';

import 'copy_to_clipboard_types.dart';

Future<CopyToClipboardResult> copyToClipboard(String text) async {
  try {
    await Clipboard.setData(ClipboardData(text: text));
    return CopyToClipboardResult.copied;
  } catch (_) {
    return CopyToClipboardResult.failed;
  }
}
