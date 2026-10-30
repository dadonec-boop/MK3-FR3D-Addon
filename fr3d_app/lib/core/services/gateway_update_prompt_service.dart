import 'dart:async';

import 'package:flutter/material.dart';
import 'package:get/get.dart';

import '../models/gateway_update_offer.dart';
import '../utils/open_external_url.dart';
import 'gateway_command_service.dart';
import 'gateway_link_service.dart';
import 'gateway_session_service.dart';
import 'language_service.dart';

/// On app start, after the gateway is online, offer program and/or LAN UI updates.
class GatewayUpdatePromptService extends GetxService {
  static GatewayUpdatePromptService get to => Get.find<GatewayUpdatePromptService>();

  final GatewaySessionService _session = GatewaySessionService.to;

  Worker? _onlineWorker;
  Worker? _keyWorker;
  Worker? _hostWorker;
  var _armed = false;
  var _inFlight = false;
  String _doneForKey = '';
  String _uiDoneForKey = '';

  void startWhenReady() {
    if (_armed) return;
    _armed = true;
    _onlineWorker = ever<bool>(_session.online, (_) => unawaited(_maybeCheck()));
    _keyWorker = ever<String>(_session.gatewayKey, (_) {
      _doneForKey = '';
      _uiDoneForKey = '';
      unawaited(_maybeCheck());
    });
    _hostWorker = ever<String>(_session.hostType, (_) => unawaited(_maybeCheck()));
    unawaited(_maybeCheck());
  }

  @override
  void onClose() {
    _onlineWorker?.dispose();
    _keyWorker?.dispose();
    _hostWorker?.dispose();
    super.onClose();
  }

  Future<void> _maybeCheck() async {
    if (_inFlight) return;
    if (!_session.isPaired || !_session.online.value) return;
    if (!_session.isWindowsHost && !_session.isLinuxGatewayHost) return;
    final key = _session.gatewayKey.value.trim();
    if (key.isEmpty) return;
    if (!Get.isRegistered<GatewayLinkService>() ||
        !GatewayLinkService.to.canSendCommands) {
      return;
    }
    if (!Get.isRegistered<GatewayCommandService>()) return;

    _inFlight = true;
    try {
      await Future<void>.delayed(const Duration(seconds: 2));
      if (!_session.isPaired || !_session.online.value) return;
      if (!_session.isWindowsHost && !_session.isLinuxGatewayHost) return;
      if (Get.isDialogOpen == true) {
        await Future<void>.delayed(const Duration(seconds: 3));
      }

      final windows = _session.isWindowsHost;
      if (key != _doneForKey) {
        final cmd = windows ? 'WINDOWS UPDATE CHECK' : 'PI UPDATE CHECK';
        final result = await GatewayCommandService.to.runCommand(
          cmd,
          logToConsole: true,
          userInitiated: false,
          bypassRoleCheck: true,
          timeoutSeconds: 45,
        );
        final offer = GatewayUpdateOffer.parse(
          result.lines,
          windowsHost: windows,
        );
        _doneForKey = key;
        if (offer != null) {
          await _prompt(offer);
        }
      }

      // UI LAN: Pi / UNO Q (nube o LAN).
      if (!windows &&
          _session.isLinuxGatewayHost &&
          key != _uiDoneForKey) {
        if (Get.isDialogOpen == true) {
          await Future<void>.delayed(const Duration(seconds: 2));
        }
        final uiResult = await GatewayCommandService.to.runCommand(
          'PI UPDATE UI CHECK',
          logToConsole: true,
          userInitiated: false,
          bypassRoleCheck: true,
          timeoutSeconds: 45,
        );
        final uiOffer = GatewayUpdateOffer.parseUi(uiResult.lines);
        _uiDoneForKey = key;
        if (uiOffer != null) {
          await _promptUi(uiOffer);
        }
      }
    } catch (e) {
      debugPrint('[GatewayUpdate] check skipped: $e');
    } finally {
      _inFlight = false;
    }
  }

  Future<void> _prompt(GatewayUpdateOffer offer) async {
    final lang = LanguageService.to;
    final accepted = await Get.dialog<bool>(
          AlertDialog(
            title: Text(lang.gatewayUpdateTitle),
            content: Text(
              offer.windowsHost
                  ? lang.gatewayUpdateWindowsBody(
                      offer.localVersion,
                      offer.remoteVersion,
                    )
                  : lang.gatewayUpdatePiBody(
                      offer.localVersion,
                      offer.remoteVersion,
                    ),
            ),
            actions: [
              TextButton(
                onPressed: () => Get.back(result: false),
                child: Text(lang.gatewayUpdateNo),
              ),
              FilledButton(
                onPressed: () => Get.back(result: true),
                child: Text(lang.gatewayUpdateYes),
              ),
            ],
          ),
          barrierDismissible: false,
        ) ??
        false;
    if (!accepted) return;

    if (offer.windowsHost) {
      await _promptWindowsDownload(offer);
      return;
    }

    try {
      await GatewayCommandService.to.runCommand(
        'PI UPDATE GATEWAY latest',
        logToConsole: true,
        userInitiated: true,
        bypassRoleCheck: true,
        timeoutSeconds: 30,
      );
      if (Get.context != null) {
        await Get.dialog<void>(
          AlertDialog(
            title: Text(lang.gatewayUpdateTitle),
            content: Text(lang.gatewayUpdateStarted),
            actions: [
              FilledButton(
                onPressed: Get.back,
                child: Text(lang.close),
              ),
            ],
          ),
        );
      }
    } catch (e) {
      debugPrint('[GatewayUpdate] apply failed: $e');
    }
  }

  Future<void> _promptUi(GatewayUpdateOffer offer) async {
    final lang = LanguageService.to;
    final accepted = await Get.dialog<bool>(
          AlertDialog(
            title: Text(lang.webUiUpdateTitle),
            content: Text(
              lang.webUiUpdateBody(offer.localVersion, offer.remoteVersion),
            ),
            actions: [
              TextButton(
                onPressed: () => Get.back(result: false),
                child: Text(lang.gatewayUpdateNo),
              ),
              FilledButton(
                onPressed: () => Get.back(result: true),
                child: Text(lang.gatewayUpdateYes),
              ),
            ],
          ),
          barrierDismissible: false,
        ) ??
        false;
    if (!accepted) return;

    try {
      await GatewayCommandService.to.runCommand(
        'PI UPDATE UI latest',
        logToConsole: true,
        userInitiated: true,
        bypassRoleCheck: true,
        timeoutSeconds: 30,
      );
      if (Get.context != null) {
        await Get.dialog<void>(
          AlertDialog(
            title: Text(lang.webUiUpdateTitle),
            content: Text(lang.webUiUpdateStarted),
            actions: [
              FilledButton(
                onPressed: Get.back,
                child: Text(lang.close),
              ),
            ],
          ),
        );
      }
    } catch (e) {
      debugPrint('[GatewayUpdate] UI apply failed: $e');
    }
  }

  Future<void> _promptWindowsDownload(GatewayUpdateOffer offer) async {
    final lang = LanguageService.to;
    await Get.dialog<void>(
      AlertDialog(
        title: Text(lang.gatewayUpdateTitle),
        content: Text(lang.gatewayUpdateWindowsHowto),
        actions: [
          TextButton(
            onPressed: Get.back,
            child: Text(lang.close),
          ),
          if (offer.zipUrl.isNotEmpty)
            FilledButton(
              onPressed: () {
                unawaited(openExternalUrl(offer.zipUrl));
              },
              child: Text(lang.gatewayUpdateDownload),
            ),
        ],
      ),
    );
  }
}
