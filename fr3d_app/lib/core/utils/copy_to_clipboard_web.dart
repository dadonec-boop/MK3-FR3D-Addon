import 'dart:html' as html;

import 'package:flutter/services.dart';

import 'copy_to_clipboard_types.dart';

Future<CopyToClipboardResult> copyToClipboard(String text) async {
  // 1) Clipboard API (HTTPS / localhost).
  try {
    final clip = html.window.navigator.clipboard;
    if (clip != null) {
      await clip.writeText(text);
      return CopyToClipboardResult.copied;
    }
  } catch (_) {}

  try {
    await Clipboard.setData(ClipboardData(text: text));
  } catch (_) {}

  // 2) Legacy execCommand — works from a user gesture on many HTTP origins.
  try {
    final ta = html.TextAreaElement()
      ..value = text
      ..readOnly = true
      ..style.position = 'fixed'
      ..style.left = '-9999px'
      ..style.top = '0';
    html.document.body?.append(ta);
    ta.focus();
    ta.select();
    ta.setSelectionRange(0, text.length);
    final ok = html.document.execCommand('copy');
    ta.remove();
    if (ok) return CopyToClipboardResult.copied;
  } catch (_) {}

  // 3) Download so the operator still gets the log on HTTP LAN.
  try {
    final stamp = DateTime.now()
        .toIso8601String()
        .replaceAll(':', '')
        .replaceAll('.', '')
        .replaceAll('-', '');
    final blob = html.Blob([text], 'text/plain');
    final url = html.Url.createObjectUrlFromBlob(blob);
    final a = html.AnchorElement(href: url)
      ..download = 'fr3d-console-log-$stamp.txt'
      ..style.display = 'none';
    html.document.body?.append(a);
    a.click();
    a.remove();
    html.Url.revokeObjectUrl(url);
    return CopyToClipboardResult.downloaded;
  } catch (_) {
    return CopyToClipboardResult.failed;
  }
}
