import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:get/get.dart';
import 'package:shared_preferences/shared_preferences.dart';

import '../../../core/models/console_log_line.dart';
import '../../../core/services/console_log_service.dart';
import '../../../core/services/language_service.dart';
import '../../../core/services/gateway_command_service.dart';
import '../../../core/services/gateway_link_service.dart';
import '../../../core/services/gateway_session_service.dart';
import '../../../core/services/user_profile_service.dart';
import '../../../core/utils/copy_to_clipboard.dart';
import '../../admin/widgets/user_management_dialog.dart' as admin_ui;
import '../../pairing/widgets/gateway_picker_panel.dart';

class ConsoleController extends GetxController {
  final GatewaySessionService _session = GatewaySessionService.to;
  final GatewayCommandService _commands = GatewayCommandService.to;
  final ConsoleLogService _consoleLog = ConsoleLogService.to;
  final UserProfileService _profiles = UserProfileService.to;

  final ScrollController scrollController = ScrollController();
  final commandController = TextEditingController();
  final commandFocus = FocusNode();

  final RxString commandError = ''.obs;

  static const _historyKey = 'fr3d_console_cmd_history';
  static const _historyMax = 10;
  final List<String> _history = [];
  int? _historyIndex;
  String _historyDraft = '';

  RxList<ConsoleLogLine> get lines => _consoleLog.lines;
  RxBool get isOnline => _session.online;
  /// Spinner del botón Enviar (solo comandos manuales del operador).
  RxBool get userCommandPending => _commands.userCommandPending;
  /// Canal Firebase ocupado (poll automático o comando en curso).
  bool get isChannelBusy => _commands.sending.value;
  bool get canSendCommands =>
      Get.isRegistered<GatewayLinkService>() &&
      GatewayLinkService.to.canSendCommands;
  String get connectionStatus => _session.connectionStatus;
  String get gatewayLabel => _session.displayName;
  String get hostname => _session.hostname.value;
  String get currentToken => _session.token.value;
  String get roleLabel => _profiles.roleLabel;
  bool get canManageUsers => _profiles.canManageUsers;
  bool get isOperator => _profiles.isOperator;
  bool get canUseConsoleFreeText => _profiles.canUseConsoleFreeText;
  bool get canSeeConsoleHelp => _profiles.canSeeConsoleHelp;
  bool get canRunOsCriticalCommands => _profiles.canRunOsCriticalCommands;
  bool get canRunPiUpdateCommands => _profiles.canRunPiUpdateCommands;

  /// OTA en gateway Linux (Pi / UNO Q); no Windows.
  bool get showPiUpdateChips =>
      canRunPiUpdateCommands && !_session.isWindowsHost;

  /// WIFI nmcli en gateway Linux (Pi / UNO Q).
  bool get showWifiChip => !_session.isWindowsHost;

  /// CHECK/HOWTO Windows: solo host Windows (todos los perfiles).
  bool get showWindowsUpdateChips =>
      _profiles.canRunWindowsUpdateCommands && _session.isWindowsHost;

  @override
  void onInit() {
    super.onInit();
    ever(_consoleLog.lines, (_) => _scrollToBottom());
    commandFocus.onKeyEvent = _onCommandKey;
    unawaited(_loadHistory());
    _consoleLog.add(
      type: ConsoleLogType.system,
      tag: 'FR3D',
      message: _readyMessage(),
    );
  }

  String _readyMessage() {
    final lang = LanguageService.to;
    if (isOperator) return lang.consoleReadyOperator;
    if (!canRunOsCriticalCommands) return lang.consoleReadyAdmin;
    return lang.consoleReady;
  }

  Future<void> sendCommand() async {
    commandError.value = '';
    final text = commandController.text;
    if (text.trim().isEmpty) return;
    if (!canSendCommands) {
      final msg = LanguageService.to.gatewayOfflineCannotSend;
      commandError.value = msg;
      _consoleLog.add(type: ConsoleLogType.system, tag: 'CMD', message: msg);
      return;
    }

    final consoleBlock = _profiles.consoleRestrictionMessage(text);
    if (consoleBlock != null) {
      commandError.value = consoleBlock;
      _consoleLog.add(type: ConsoleLogType.error, tag: 'CMD', message: consoleBlock);
      return;
    }

    try {
      _recordHistory(text);
      await _commands.sendCommand(text);
      commandController.clear();
    } catch (e) {
      final msg = _formatCommandError(e);
      commandError.value = msg;
      _consoleLog.add(type: ConsoleLogType.error, tag: 'CMD', message: msg);
    }
  }

  String _formatCommandError(Object e) {
    var text = e.toString();
    if (text.startsWith('Bad state: ')) {
      text = text.substring('Bad state: '.length);
    } else if (text.startsWith('StateError: ')) {
      text = text.substring('StateError: '.length);
    }
    if (text.contains('Wait for the previous command response')) {
      return LanguageService.to.gatewayBusyWait;
    }
    return text;
  }

  void sendQuick(String text) {
    commandController.text = text;
    sendCommand();
  }

  Future<void> unpair() async {
    await _session.unpair();
  }

  Future<void> showChangeTokenDialog(BuildContext context) async {
    await showGatewayPickerDialog(
      context: context,
      title: LanguageService.to.changeGatewayDialogTitle,
      currentToken: currentToken,
      onSelect: _session.changeToken,
    );
  }

  Future<void> openUserManagement(BuildContext context) async {
    await admin_ui.showUserManagementDialog(context);
  }

  void clearLogs() => _consoleLog.clear();

  String formatLogLine(ConsoleLogLine line) =>
      '[${line.formattedTime}] [${line.tag}] ${line.message}';

  Future<void> copyLogsToClipboard(BuildContext context) async {
    final lang = LanguageService.to;
    final snapshot = List<ConsoleLogLine>.from(lines);
    if (snapshot.isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text(lang.consoleLogEmpty)),
      );
      return;
    }
    final text = snapshot.map(formatLogLine).join('\n');
    final result = await copyToClipboard(text);
    if (!context.mounted) return;
    final message = switch (result) {
      CopyToClipboardResult.copied => lang.consoleLogCopied,
      CopyToClipboardResult.downloaded => lang.consoleLogDownloaded,
      CopyToClipboardResult.failed => lang.consoleLogCopyFailed,
    };
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(content: Text(message)),
    );
  }

  Future<void> copyLogLineToClipboard(
    BuildContext context,
    ConsoleLogLine line,
  ) async {
    final lang = LanguageService.to;
    final result = await copyToClipboard(formatLogLine(line));
    if (!context.mounted) return;
    final message = switch (result) {
      CopyToClipboardResult.copied => lang.consoleLineCopied,
      CopyToClipboardResult.downloaded => lang.consoleLogDownloaded,
      CopyToClipboardResult.failed => lang.consoleLogCopyFailed,
    };
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(content: Text(message)),
    );
  }

  RxBool get showAutomaticCommands => _consoleLog.showAutomaticCommands;

  void toggleAutomaticCommandLogs() {
    _consoleLog.showAutomaticCommands.value = !_consoleLog.showAutomaticCommands.value;
    _consoleLog.add(
      type: ConsoleLogType.system,
      tag: 'FR3D',
      message: _consoleLog.showAutomaticCommands.value
          ? LanguageService.to.consoleAutoShown
          : LanguageService.to.consoleAutoHidden,
    );
  }

  void _scrollToBottom() {
    if (!scrollController.hasClients) return;
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (!scrollController.hasClients) return;
      scrollController.animateTo(
        scrollController.position.maxScrollExtent,
        duration: const Duration(milliseconds: 200),
        curve: Curves.easeOut,
      );
    });
  }

  KeyEventResult _onCommandKey(FocusNode node, KeyEvent event) {
    if (event is! KeyDownEvent && event is! KeyRepeatEvent) {
      return KeyEventResult.ignored;
    }
    if (event.logicalKey == LogicalKeyboardKey.arrowUp) {
      historyOlder();
      return KeyEventResult.handled;
    }
    if (event.logicalKey == LogicalKeyboardKey.arrowDown) {
      historyNewer();
      return KeyEventResult.handled;
    }
    return KeyEventResult.ignored;
  }

  void historyOlder() {
    if (_history.isEmpty) return;
    if (_historyIndex == null) {
      _historyDraft = commandController.text;
      _historyIndex = _history.length - 1;
    } else if (_historyIndex! > 0) {
      _historyIndex = _historyIndex! - 1;
    }
    _applyHistory();
  }

  void historyNewer() {
    if (_historyIndex == null) return;
    if (_historyIndex! < _history.length - 1) {
      _historyIndex = _historyIndex! + 1;
      _applyHistory();
      return;
    }
    _historyIndex = null;
    _setCommandText(_historyDraft);
  }

  void _applyHistory() {
    final i = _historyIndex;
    if (i == null || i < 0 || i >= _history.length) return;
    _setCommandText(_history[i]);
  }

  void _setCommandText(String text) {
    commandController.value = TextEditingValue(
      text: text,
      selection: TextSelection.collapsed(offset: text.length),
    );
  }

  void _recordHistory(String raw) {
    final t = raw.trim();
    if (t.isEmpty) return;
    if (_history.isNotEmpty && _history.last == t) {
      _historyIndex = null;
      return;
    }
    _history.add(t);
    while (_history.length > _historyMax) {
      _history.removeAt(0);
    }
    _historyIndex = null;
    unawaited(_saveHistory());
  }

  Future<void> _loadHistory() async {
    final prefs = await SharedPreferences.getInstance();
    final stored = prefs.getStringList(_historyKey) ?? const <String>[];
    _history
      ..clear()
      ..addAll(stored.where((e) => e.trim().isNotEmpty).take(_historyMax));
  }

  Future<void> _saveHistory() async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setStringList(_historyKey, List<String>.from(_history));
  }

  @override
  void onClose() {
    commandController.dispose();
    commandFocus.dispose();
    scrollController.dispose();
    super.onClose();
  }
}
