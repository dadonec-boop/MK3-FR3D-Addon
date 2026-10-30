import 'package:flutter/material.dart';
import 'package:get/get.dart';

import '../../../core/services/gateway_command_service.dart';
import '../../../core/services/gateway_session_service.dart';
import '../../../core/services/language_service.dart';
import '../models/serial_port_snapshot.dart';

class SerialComController extends GetxController {
  final GatewayCommandService _commands = GatewayCommandService.to;
  final GatewaySessionService _session = GatewaySessionService.to;

  final availablePorts = <String>[].obs;
  final activePort = ''.obs;
  final hostType = ''.obs;
  final selectedPort = ''.obs;
  final manualPortController = TextEditingController();
  final busy = false.obs;
  final lastError = ''.obs;
  final lastInfo = ''.obs;
  final windowsHost = false.obs;

  bool get isPaired => _session.isPaired;

  @override
  void onInit() {
    super.onInit();
    ever(_session.gatewayKey, (_) {
      if (_session.isPaired) {
        resetForGatewayChange();
        _syncHostFromPresence();
        refreshPorts();
      }
    });
    ever(_session.hostType, (_) => _syncHostFromPresence());
    if (isPaired) {
      _syncHostFromPresence();
      refreshPorts();
    }
  }

  void _syncHostFromPresence() {
    final ht = _session.hostType.value.trim().toLowerCase();
    if (ht.isNotEmpty) {
      hostType.value = ht;
    }
    if (_session.isWindowsHost || ht.contains('windows')) {
      windowsHost.value = true;
    }
  }

  @override
  void onClose() {
    manualPortController.dispose();
    super.onClose();
  }

  void resetForGatewayChange() {
    availablePorts.clear();
    activePort.value = '';
    hostType.value = '';
    selectedPort.value = '';
    manualPortController.clear();
    busy.value = false;
    lastError.value = '';
    lastInfo.value = '';
    windowsHost.value = false;
  }

  Future<void> refreshPorts() async {
    if (!isPaired || busy.value) return;
    busy.value = true;
    lastError.value = '';
    lastInfo.value = '';
    _syncHostFromPresence();
    try {
      final result = await _commands.runCommand(
        'SERIAL LIST',
        logToConsole: false,
        userInitiated: true,
        timeoutSeconds: 30,
      );
      final snap = SerialPortSnapshot.fromCommandLines(result.lines);
      if (snap.hostType.isNotEmpty) {
        hostType.value = snap.hostType;
      }
      windowsHost.value = snap.isWindowsHost ||
          snap.hostType.toLowerCase().contains('windows') ||
          _session.isWindowsHost;
      activePort.value = snap.activePort;
      availablePorts.assignAll(snap.ports);
      if (snap.activePort.isNotEmpty) {
        selectedPort.value = snap.activePort;
        manualPortController.text = snap.activePort;
      } else if (snap.ports.isNotEmpty) {
        selectedPort.value = snap.ports.first;
        manualPortController.text = snap.ports.first;
      }
      if (!windowsHost.value &&
          (hostType.value.trim().toLowerCase() == 'raspberry_pi' ||
              hostType.value.trim().toLowerCase() == 'uno_q')) {
        lastInfo.value = LanguageService.to.serialComWindowsOnly;
      }
    } catch (e) {
      lastError.value = e.toString();
      // Keep the form usable: presence may already say Windows.
      _syncHostFromPresence();
    } finally {
      busy.value = false;
    }
  }

  Future<void> applySelectedPort() async {
    if (!isPaired || busy.value) return;
    final port = (selectedPort.value.trim().isNotEmpty
            ? selectedPort.value
            : manualPortController.text)
        .trim();
    if (port.isEmpty) {
      lastError.value = LanguageService.to.serialComEmptyPort;
      return;
    }
    busy.value = true;
    lastError.value = '';
    lastInfo.value = '';
    try {
      final result = await _commands.runCommand(
        'SERIAL SET PORT $port',
        logToConsole: true,
        userInitiated: true,
        timeoutSeconds: 45,
      );
      lastInfo.value = result.lines.where((l) => l.trim().isNotEmpty).join('\n');
    } catch (e) {
      lastError.value = e.toString();
    } finally {
      busy.value = false;
    }
    if (lastError.value.isEmpty) {
      await refreshPorts();
    }
  }
}
