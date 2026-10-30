import 'package:flutter/material.dart';
import 'package:get/get.dart';

import '../../../core/constants/fr3d_light_theme.dart';
import '../../../core/help/help_ids.dart';
import '../../../core/services/language_service.dart';
import '../../shell/widgets/fr3d_panel_card.dart';
import '../controllers/lcd_controller.dart';

class LcdTabView extends StatefulWidget {
  const LcdTabView({super.key});

  @override
  State<LcdTabView> createState() => _LcdTabViewState();
}

class _LcdTabViewState extends State<LcdTabView> {
  LcdController get c => Get.find<LcdController>();

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) => c.startTab());
  }

  @override
  void dispose() {
    if (Get.isRegistered<LcdController>()) {
      c.stopTab();
    }
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final lang = LanguageService.to;
    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Align(
        alignment: Alignment.topCenter,
        child: ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 720),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              Fr3dPanelCard(
                title: lang.tabLcd,
                helpTopicId: HelpIds.lcd,
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: [
                    Text(
                      lang.lcdHint,
                      style: Fr3dLightTheme.muted,
                    ),
                    const SizedBox(height: 16),
                    Obx(() {
                      final lines = c.lines.toList();
                      return _LcdPanel(lines: lines);
                    }),
                    const SizedBox(height: 20),
                    Row(
                      children: [
                        Expanded(
                          child: _HoldButton(
                            label: '◀',
                            onTap: c.encMinus,
                            onHoldStart: () => c.startHold(c.encMinusHoldTick),
                            onHoldEnd: c.stopHold,
                          ),
                        ),
                        const SizedBox(width: 12),
                        Expanded(
                          child: _HoldButton(
                            label: '●',
                            onTap: c.encClick,
                            onHoldStart: null,
                            onHoldEnd: null,
                          ),
                        ),
                        const SizedBox(width: 12),
                        Expanded(
                          child: _HoldButton(
                            label: '▶',
                            onTap: c.encPlus,
                            onHoldStart: () => c.startHold(c.encPlusHoldTick),
                            onHoldEnd: c.stopHold,
                          ),
                        ),
                      ],
                    ),
                    Align(
                      alignment: Alignment.centerLeft,
                      child: TextButton.icon(
                        onPressed: () => c.refreshLcd(),
                        icon: const Icon(Icons.refresh, size: 18),
                        label: Text(lang.lcdRefresh),
                      ),
                    ),
                    Obx(() {
                      final err = c.lastError.value;
                      if (err.isEmpty) return const SizedBox.shrink();
                      return Padding(
                        padding: const EdgeInsets.only(top: 8),
                        child: Text(
                          err,
                          style: Fr3dLightTheme.body.copyWith(
                            color: Colors.red.shade700,
                          ),
                        ),
                      );
                    }),
                  ],
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

/// Emulador HD44780 4×20: cada celda = 1 carácter (cuadrícula fija).
class _LcdPanel extends StatelessWidget {
  const _LcdPanel({required this.lines});

  final List<String> lines;

  static const _bezel = Color(0xFF1A2E1A);
  static const _border = Color(0xFF3D5C3D);
  static const _cellGap = Color(0xFF152515);
  static const _fg = Color(0xFFB8F0B8);
  static const _bgSelected = Color(0xFFB8F0B8);
  static const _fgSelected = Color(0xFF0A1A0A);

  /// Fila de menú seleccionada: '>' o '?Texto...?' (UPLEVEL custom → '?').
  static bool _isMenuSelected(String line) {
    if (line.isEmpty) return false;
    if (line.startsWith('>')) return true;
    if (line[0] != '?') return false;
    // Status: "?  0/0?" / "?123" — no es menú.
    if (line.length > 1) {
      final c1 = line[1];
      if (c1 == ' ' || (c1.compareTo('0') >= 0 && c1.compareTo('9') <= 0)) {
        return false;
      }
    }
    // "?AddonFR3D     ?" — marcadores custom a ambos lados.
    final trimmedEnd = line.trimRight();
    return trimmedEnd.length >= 2 && trimmedEnd.endsWith('?');
  }

  /// HD44780 0x7E = flecha derecha de submenú (en ASCII llega como '~').
  static String _glyph(String ch, {required bool selected}) {
    if (ch == '~') return '►';
    // Custom / UPLEVEL / iconos status → celda vacía (ya limpios en selección).
    if (ch == '?') return ' ';
    if (ch == '>' && selected) return ' ';
    return ch;
  }

  static List<String> _cellsForLine(String raw) {
    final selected = _isMenuSelected(raw);
    var s = raw.padRight(LcdController.cols);
    if (s.length > LcdController.cols) {
      s = s.substring(0, LcdController.cols);
    }
    final chars = List<String>.generate(LcdController.cols, (i) => s[i]);
    if (selected) {
      if (chars[0] == '>' || chars[0] == '?') chars[0] = ' ';
      // UPLEVEL derecho (custom '?'), no tocar flecha de submenú '~'.
      for (var i = chars.length - 1; i >= 1; i--) {
        if (chars[i] == ' ') continue;
        if (chars[i] == '?') chars[i] = ' ';
        break;
      }
    }
    return [
      for (final c in chars) _glyph(c, selected: selected),
    ];
  }

  @override
  Widget build(BuildContext context) {
    return LayoutBuilder(
      builder: (context, constraints) {
        final maxW = constraints.maxWidth.isFinite
            ? constraints.maxWidth
            : 480.0;
        // 20 cols × ~0.55 aspect típico HD44780 + gap interno.
        final cellW = ((maxW - 16) / LcdController.cols).clamp(10.0, 22.0);
        final cellH = cellW * 1.55;
        final fontSize = (cellW * 0.78).clamp(9.0, 16.0);

        return Container(
          padding: const EdgeInsets.all(8),
          decoration: BoxDecoration(
            color: _bezel,
            borderRadius: BorderRadius.circular(8),
            border: Border.all(color: _border),
          ),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              for (var r = 0; r < LcdController.rows; r++) ...[
                if (r > 0) const SizedBox(height: 2),
                _LcdCharRow(
                  cells: _cellsForLine(
                    r < lines.length ? lines[r] : ' ' * LcdController.cols,
                  ),
                  selected: _isMenuSelected(
                    r < lines.length ? lines[r] : '',
                  ),
                  cellW: cellW,
                  cellH: cellH,
                  fontSize: fontSize,
                  fg: _fg,
                  fgSelected: _fgSelected,
                  bgSelected: _bgSelected,
                  cellGap: _cellGap,
                ),
              ],
            ],
          ),
        );
      },
    );
  }
}

class _LcdCharRow extends StatelessWidget {
  const _LcdCharRow({
    required this.cells,
    required this.selected,
    required this.cellW,
    required this.cellH,
    required this.fontSize,
    required this.fg,
    required this.fgSelected,
    required this.bgSelected,
    required this.cellGap,
  });

  final List<String> cells;
  final bool selected;
  final double cellW;
  final double cellH;
  final double fontSize;
  final Color fg;
  final Color fgSelected;
  final Color bgSelected;
  final Color cellGap;

  @override
  Widget build(BuildContext context) {
    final ink = selected ? fgSelected : fg;
    final fill = selected ? bgSelected : const Color(0xFF1F3A1F);
    return Row(
      mainAxisAlignment: MainAxisAlignment.center,
      children: [
        for (var i = 0; i < cells.length; i++) ...[
          if (i > 0) SizedBox(width: 1, height: cellH, child: ColoredBox(color: cellGap)),
          SizedBox(
            width: cellW,
            height: cellH,
            child: ColoredBox(
              color: fill,
              child: Center(
                child: Text(
                  cells[i] == ' ' ? '' : cells[i],
                  textAlign: TextAlign.center,
                  style: TextStyle(
                    fontFamily: 'Consolas',
                    fontFamilyFallback: const [
                      'Courier New',
                      'monospace',
                    ],
                    fontSize: fontSize,
                    height: 1.0,
                    fontWeight: FontWeight.w600,
                    color: ink,
                    letterSpacing: 0,
                  ),
                ),
              ),
            ),
          ),
        ],
      ],
    );
  }
}

class _HoldButton extends StatelessWidget {
  const _HoldButton({
    required this.label,
    required this.onTap,
    required this.onHoldStart,
    required this.onHoldEnd,
  });

  final String label;
  final Future<void> Function() onTap;
  final VoidCallback? onHoldStart;
  final VoidCallback? onHoldEnd;

  @override
  Widget build(BuildContext context) {
    return Listener(
      onPointerDown: onHoldStart == null
          ? null
          : (_) => onHoldStart!(),
      onPointerUp: onHoldEnd == null ? null : (_) => onHoldEnd!(),
      onPointerCancel: onHoldEnd == null ? null : (_) => onHoldEnd!(),
      child: SizedBox(
        height: 52,
        child: ElevatedButton(
          onPressed: onHoldStart == null ? () => onTap() : () {},
          child: Text(label, style: const TextStyle(fontSize: 22)),
        ),
      ),
    );
  }
}