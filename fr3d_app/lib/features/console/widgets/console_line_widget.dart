import 'package:flutter/material.dart';
import 'package:get/get.dart';

import '../../../core/constants/console_theme.dart';
import '../../../core/models/console_log_line.dart';
import '../../../core/utils/copy_to_clipboard.dart';
import '../../../core/utils/open_external_url.dart';
import '../controllers/console_controller.dart';

class ConsoleLineWidget extends StatelessWidget {
  const ConsoleLineWidget({super.key, required this.line});

  final ConsoleLogLine line;

  static final RegExp _urlRe = RegExp(r'https?://[^\s<>"\]]+');

  Future<void> _openUrl(BuildContext context, String url) async {
    final ok = await openExternalUrl(url);
    if (ok) return;

    final result = await copyToClipboard(url);
    if (!context.mounted) return;
    if (result == CopyToClipboardResult.failed) return;
    Get.snackbar(
      'Download',
      result == CopyToClipboardResult.copied
          ? 'Could not open the link. URL copied — paste it in your browser.'
          : 'Could not open the link. URL saved as a downloaded .txt.',
      snackPosition: SnackPosition.BOTTOM,
      duration: const Duration(seconds: 5),
    );
  }

  List<InlineSpan> _messageSpans(BuildContext context, String message, TextStyle baseStyle) {
    final spans = <InlineSpan>[];
    var start = 0;
    for (final match in _urlRe.allMatches(message)) {
      if (match.start > start) {
        spans.add(TextSpan(text: message.substring(start, match.start)));
      }
      var url = match.group(0)!;
      while (url.isNotEmpty && '.,;:)'.contains(url[url.length - 1])) {
        url = url.substring(0, url.length - 1);
      }
      final trailing = match.group(0)!.substring(url.length);
      spans.add(
        WidgetSpan(
          alignment: PlaceholderAlignment.baseline,
          baseline: TextBaseline.alphabetic,
          child: MouseRegion(
            cursor: SystemMouseCursors.click,
            child: GestureDetector(
              onTap: () => _openUrl(context, url),
              child: Text(
                url,
                style: baseStyle.copyWith(
                  color: ConsoleTheme.outgoing,
                  decoration: TextDecoration.underline,
                  decorationColor: ConsoleTheme.outgoing,
                ),
              ),
            ),
          ),
        ),
      );
      if (trailing.isNotEmpty) {
        spans.add(TextSpan(text: trailing));
      }
      start = match.end;
    }
    if (start < message.length) {
      spans.add(TextSpan(text: message.substring(start)));
    }
    return spans;
  }

  @override
  Widget build(BuildContext context) {
    final controller = Get.find<ConsoleController>();
    final baseStyle = ConsoleTheme.mono.copyWith(color: ConsoleTheme.textPrimary);
    return InkWell(
      onLongPress: () => controller.copyLogLineToClipboard(context, line),
      child: Padding(
        padding: const EdgeInsets.symmetric(vertical: 2),
        child: Text.rich(
          TextSpan(
            style: baseStyle,
            children: [
              TextSpan(
                text: '[${line.formattedTime}] ',
                style: ConsoleTheme.mono.copyWith(color: ConsoleTheme.textMuted),
              ),
              TextSpan(
                text: '[${line.tag}] ',
                style: ConsoleTheme.mono.copyWith(
                  color: _colorForType(line.type),
                  fontWeight: FontWeight.bold,
                ),
              ),
              ..._messageSpans(context, line.message, baseStyle),
            ],
          ),
        ),
      ),
    );
  }

  Color _colorForType(ConsoleLogType type) {
    return switch (type) {
      ConsoleLogType.incoming => ConsoleTheme.incoming,
      ConsoleLogType.outgoing => ConsoleTheme.outgoing,
      ConsoleLogType.system => ConsoleTheme.system,
      ConsoleLogType.success => ConsoleTheme.success,
      ConsoleLogType.error => ConsoleTheme.error,
    };
  }
}
