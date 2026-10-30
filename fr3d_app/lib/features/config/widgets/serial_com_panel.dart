import 'package:flutter/material.dart';
import 'package:get/get.dart';

import '../../../core/constants/fr3d_light_theme.dart';
import '../../../core/help/help_ids.dart';
import '../../../core/services/gateway_session_service.dart';
import '../../../core/services/language_service.dart';
import '../../shell/widgets/fr3d_panel_card.dart';
import '../controllers/serial_com_controller.dart';

class SerialComPanel extends GetView<SerialComController> {
  const SerialComPanel({super.key});

  @override
  Widget build(BuildContext context) {
    return Obx(() {
      final lang = LanguageService.to;
      lang.code.value;
      final session = GatewaySessionService.to;
      final paired =
          session.gatewayKey.value.isNotEmpty && session.token.value.isNotEmpty;

      return Fr3dPanelCard(
        title: lang.serialComTitle,
        helpTopicId: HelpIds.configSerialCom,
        child: !paired
            ? Text(lang.wifiPairFirst, style: Fr3dLightTheme.muted)
            : Obx(() {
                lang.code.value;
                session.hostType.value;
                controller.hostType.value;
                controller.windowsHost.value;
                controller.busy.value;

                // Presence hostType=windows is enough; do not wait on SERIAL LIST.
                final fromPresence = session.isWindowsHost;
                final fromList = controller.windowsHost.value;
                final listedHost = controller.hostType.value.trim().toLowerCase();
                final isLinuxGw = session.isLinuxGatewayHost ||
                    listedHost == 'raspberry_pi' ||
                    listedHost == 'uno_q';
                final showWindowsUi = fromPresence || fromList || (!isLinuxGw && listedHost.isEmpty);

                if (isLinuxGw && !fromPresence && !fromList) {
                  return Text(
                    lang.serialComWindowsOnly,
                    style: Fr3dLightTheme.muted.copyWith(
                      color: Colors.orange.shade800,
                    ),
                  );
                }
                if (!showWindowsUi) {
                  return Text(
                    lang.serialComWindowsOnly,
                    style: Fr3dLightTheme.muted.copyWith(
                      color: Colors.orange.shade800,
                    ),
                  );
                }

                final busy = controller.busy.value;
                final ports = controller.availablePorts.toList();
                final selected = controller.selectedPort.value;

                return Column(
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: [
                    Text(
                      lang.serialComHint,
                      style: Fr3dLightTheme.muted.copyWith(fontSize: 12),
                    ),
                    const SizedBox(height: 12),
                    _InfoRow(
                      label: lang.serialComActive,
                      value: controller.activePort.value.isEmpty
                          ? '—'
                          : controller.activePort.value,
                    ),
                    const SizedBox(height: 12),
                    Row(
                      children: [
                        Expanded(
                          child: ports.isEmpty
                              ? TextField(
                                  controller: controller.manualPortController,
                                  enabled: !busy,
                                  decoration: InputDecoration(
                                    labelText: lang.serialComPort,
                                    hintText: 'COM6',
                                    isDense: true,
                                    border: const OutlineInputBorder(),
                                  ),
                                  onChanged: (v) =>
                                      controller.selectedPort.value = v.trim(),
                                )
                              : DropdownButtonFormField<String>(
                                  key: ValueKey(
                                    '${selected}_${ports.join(',')}',
                                  ),
                                  initialValue: ports.contains(selected)
                                      ? selected
                                      : ports.first,
                                  decoration: InputDecoration(
                                    labelText: lang.serialComPort,
                                    isDense: true,
                                    border: const OutlineInputBorder(),
                                  ),
                                  items: [
                                    for (final p in ports)
                                      DropdownMenuItem(
                                        value: p,
                                        child: Text(p),
                                      ),
                                  ],
                                  onChanged: busy
                                      ? null
                                      : (v) {
                                          if (v == null) return;
                                          controller.selectedPort.value = v;
                                          controller.manualPortController.text =
                                              v;
                                        },
                                ),
                        ),
                        const SizedBox(width: 8),
                        OutlinedButton(
                          onPressed: busy ? null : controller.refreshPorts,
                          child: Text(lang.refresh),
                        ),
                      ],
                    ),
                    if (ports.isNotEmpty) ...[
                      const SizedBox(height: 8),
                      TextField(
                        controller: controller.manualPortController,
                        enabled: !busy,
                        decoration: InputDecoration(
                          labelText: lang.serialComManual,
                          hintText: 'COM6',
                          isDense: true,
                          border: const OutlineInputBorder(),
                        ),
                        onChanged: (v) =>
                            controller.selectedPort.value = v.trim(),
                      ),
                    ],
                    const SizedBox(height: 12),
                    Align(
                      alignment: Alignment.centerLeft,
                      child: ElevatedButton(
                        onPressed: busy ? null : controller.applySelectedPort,
                        child: Text(lang.serialComApply),
                      ),
                    ),
                    Obx(() {
                      final err = controller.lastError.value;
                      final info = controller.lastInfo.value;
                      if (err.isEmpty && info.isEmpty) {
                        return const SizedBox.shrink();
                      }
                      return Padding(
                        padding: const EdgeInsets.only(top: 10),
                        child: Text(
                          err.isNotEmpty ? err : info,
                          style: Fr3dLightTheme.body.copyWith(
                            color: err.isNotEmpty
                                ? Colors.red.shade700
                                : Fr3dLightTheme.textPrimary,
                            fontSize: 12,
                          ),
                        ),
                      );
                    }),
                    if (busy) ...[
                      const SizedBox(height: 10),
                      const LinearProgressIndicator(),
                    ],
                  ],
                );
              }),
      );
    });
  }
}

class _InfoRow extends StatelessWidget {
  const _InfoRow({required this.label, required this.value});

  final String label;
  final String value;

  @override
  Widget build(BuildContext context) {
    return Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        SizedBox(
          width: 110,
          child: Text(label, style: Fr3dLightTheme.muted),
        ),
        Expanded(
          child: SelectableText(value, style: Fr3dLightTheme.body),
        ),
      ],
    );
  }
}
