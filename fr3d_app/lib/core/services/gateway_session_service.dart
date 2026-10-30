import 'dart:async';
import 'dart:convert';

import 'package:firebase_auth/firebase_auth.dart';
import 'package:firebase_database/firebase_database.dart';
import 'package:get/get.dart';
import 'package:shared_preferences/shared_preferences.dart';

import '../config/app_config.dart';
import 'console_log_service.dart';
import '../models/console_log_line.dart';
import '../utils/gateway_label_utils.dart';
import 'gateway_app_reset.dart';
import 'gateway_control_claim_service.dart';
import 'gateway_history_service.dart';
import 'gateway_status_bus_service.dart';
import 'lan_mode_service.dart';
import 'language_service.dart';

class GatewaySessionService extends GetxService {
  static GatewaySessionService get to => Get.find<GatewaySessionService>();

  static const _userLastGatewayNode = 'userLastGateway';

  final gatewayKey = ''.obs;
  final token = ''.obs;
  final label = ''.obs;
  final userLabel = ''.obs;
  final online = false.obs;
  final hostname = ''.obs;
  final hostType = ''.obs;
  final busy = false.obs;

  StreamSubscription<DatabaseEvent>? _presenceSub;
  SharedPreferences? _prefs;

  bool get isPaired => gatewayKey.value.isNotEmpty && token.value.isNotEmpty;

  /// Sesión local (nginx + /api). No toca Firebase.
  Future<void> applyLanSession({
    required String hostname,
    required String token,
  }) async {
    await _presenceSub?.cancel();
    _presenceSub = null;
    final host = hostname.trim().isEmpty ? 'raspberry-pi' : hostname.trim();
    final tok = LanModeService.foldDisplayToken(
      preferred: token,
      seed: host,
    );
    gatewayKey.value = 'lan-local';
    this.token.value = tok;
    this.hostname.value = host;
    hostType.value = 'raspberry_pi';
    online.value = true;
    label.value = host;
    userLabel.value = '';
  }

  bool get isWindowsHost =>
      hostType.value.trim().toLowerCase() == 'windows';

  bool get isRaspberryPiHost =>
      hostType.value.trim().toLowerCase() == 'raspberry_pi';

  bool get isUnoQHost =>
      hostType.value.trim().toLowerCase() == 'uno_q';

  /// Pi o Arduino UNO Q: OTA programa/UI, LAN, comandos PI UPDATE.
  bool get isLinuxGatewayHost => isRaspberryPiHost || isUnoQHost;

  String get displayName {
    if (userLabel.value.trim().isNotEmpty) {
      return GatewayLabelUtils.display(userLabel.value, fallback: gatewayKey.value);
    }
    if (label.value.trim().isNotEmpty) {
      return GatewayLabelUtils.display(label.value, fallback: gatewayKey.value);
    }
    if (gatewayKey.value.isNotEmpty) return gatewayKey.value;
    return '';
  }

  String get connectionStatus {
    if (!isPaired) return 'sin_gateway';
    return online.value ? 'connected' : 'disconnected';
  }

  @override
  void onClose() {
    _presenceSub?.cancel();
    super.onClose();
  }

  String? _currentUid() => FirebaseAuth.instance.currentUser?.uid;

  String _sessionPrefsKey(String uid) => '${AppConfig.prefsSessionPrefix}_$uid';

  Future<void> loadSavedSession() async {
    final uid = _currentUid();
    if (uid == null) return;

    _prefs ??= await SharedPreferences.getInstance();
    await _migrateLegacySession(uid);

    final raw = _prefs!.getString(_sessionPrefsKey(uid));
    if (raw != null && raw.isNotEmpty) {
      try {
        final data = Map<String, dynamic>.from(jsonDecode(raw) as Map);
        final savedKey = (data['gatewayKey'] ?? '').toString().trim();
        final savedToken = (data['token'] ?? '').toString().trim().toUpperCase();
        if (savedKey.isNotEmpty && savedToken.isNotEmpty) {
          await _ensureGatewayAccess(uid, savedKey, savedToken);
          await _applySession(savedKey, savedToken);
          await _rememberInHistory();
          return;
        }
      } catch (_) {
        // ignore corrupt session
      }
    }
  }

  Future<bool> tryRestoreLastGateway() async {
    if (isPaired) return true;

    final uid = _currentUid();
    if (uid == null) return false;

    // 1) Historial local (incluye totems sincronizados desde Firebase al login).
    try {
      if (Get.isRegistered<GatewayHistoryService>()) {
        final recent = GatewayHistoryService.to.mostRecent;
        if (recent != null) {
          await pairWithToken(recent.token);
          return true;
        }
      }
    } catch (_) {
      // ignore and fallback to firebase
    }

    // 2) Último token usado en cualquier dispositivo (si el historial local sigue vacío).
    try {
      final lastSnap = await FirebaseDatabase.instance.ref('$_userLastGatewayNode/$uid').get();
      final raw = lastSnap.child('token').value;
      final lastToken = (raw ?? '').toString().trim().toUpperCase();
      if (lastToken.isNotEmpty && lastToken.length == AppConfig.tokenLength) {
        await pairWithToken(lastToken);
        return true;
      }
    } catch (_) {
      // ignore
    }

    // 3) Fallback: tokens autorizados en userAccess.
    // (Como no hay timestamps aquí, probamos en orden iterando el mapa.)
    try {
      final accessSnap = await FirebaseDatabase.instance.ref('userAccess/$uid').get();
      final data = accessSnap.value;
      if (data is Map) {
        for (final entry in data.entries) {
          final t = (entry.key ?? '').toString().trim().toUpperCase();
          final v = entry.value;
          final enabled = v == true || (v is num && v == 1);
          if (!enabled) continue;
          if (t.isEmpty || t.length != AppConfig.tokenLength) continue;
          try {
            await pairWithToken(t);
            return true;
          } catch (_) {
            // token not usable (revoked/stale) -> try next
          }
        }
      }
    } catch (_) {
      // ignore
    }

    return false;
  }

  Future<void> pairWithToken(String rawToken, {String userLabel = ''}) async {
    await _pairWithToken(rawToken, isTokenChange: false, userLabel: userLabel);
  }

  Future<void> changeToken(String rawToken, {String userLabel = ''}) async {
    if (!isPaired) {
      await pairWithToken(rawToken, userLabel: userLabel);
      return;
    }

    final normalized = rawToken.trim().toUpperCase();
    if (normalized == token.value) {
      if (userLabel.trim().isNotEmpty) {
        await saveGatewayLabel(normalized, userLabel);
      } else {
        throw StateError(LanguageService.to.gatewayErrAlreadyUsingToken);
      }
      return;
    }

    await _pairWithToken(rawToken, isTokenChange: true, userLabel: userLabel);
  }

  Future<void> _pairWithToken(
    String rawToken, {
    required bool isTokenChange,
    String userLabel = '',
  }) async {
    final uid = _currentUid();
    if (uid == null) {
      throw StateError(LanguageService.to.gatewayErrSignInBeforePairing);
    }

    final normalized = rawToken.trim().toUpperCase();
    if (normalized.length != AppConfig.tokenLength) {
      throw FormatException(LanguageService.to.gatewayErrTokenLength(AppConfig.tokenLength));
    }

    busy.value = true;
    try {
      final previousToken = token.value;
      final catalogSnap = await FirebaseDatabase.instance.ref('gatewaysByToken/$normalized').get();
      if (!catalogSnap.exists || catalogSnap.value == null) {
        throw StateError(LanguageService.to.gatewayErrTokenNotFound);
      }

      final catalog = Map<String, dynamic>.from(catalogSnap.value as Map);
      final key = (catalog['gatewayKey'] ?? '').toString().trim();
      if (key.isEmpty) {
        throw StateError(LanguageService.to.gatewayErrTokenNoGateway);
      }

      final accessRef = FirebaseDatabase.instance.ref('userAccess/$uid/$normalized');
      final existing = await accessRef.get();
      if (!existing.exists) {
        await accessRef.set(true);
      }

      await _ensureGatewayAccess(uid, key, normalized);

      await _applySession(key, normalized);
      await _persistSession(uid);
      await _rememberInHistory();
      await _trySaveUserLabel(normalized, userLabel);
      await _rememberLastGatewayInFirebase(uid, normalized);

      if (Get.isRegistered<GatewayStatusBusService>()) {
        GatewayStatusBusService.to.ensurePollingStarted(refreshNow: true);
      }

      if (isTokenChange) {
        GatewayAppReset.afterGatewayChange();
      }

      if (isTokenChange && previousToken.isNotEmpty && previousToken != normalized) {
        _log(
          ConsoleLogType.success,
          'PAIR',
          'Token changed: $previousToken -> $normalized (gateway $key)',
        );
      } else {
        _log(
          ConsoleLogType.success,
          'PAIR',
          'Paired with gateway $key (token $normalized)',
        );
      }
    } finally {
      busy.value = false;
    }
  }

  Future<void> _rememberLastGatewayInFirebase(String uid, String normalizedToken) async {
    final nowMs = DateTime.now().millisecondsSinceEpoch;
    // Persistimos el último token usado para que el usuario pueda restaurar en otra PC.
    await FirebaseDatabase.instance.ref('$_userLastGatewayNode/$uid').set({
      'token': normalizedToken,
      'lastUsedMs': nowMs,
    });
  }

  Future<void> unpair() async {
    await clearSession();
    _log(ConsoleLogType.system, 'PAIR', 'Gateway unpaired from this app.');
  }

  Future<void> clearSession({bool removePersisted = true}) async {
    _presenceSub?.cancel();
    _presenceSub = null;

    if (Get.isRegistered<GatewayControlClaimService>()) {
      await GatewayControlClaimService.to.releaseControl();
    }

    gatewayKey.value = '';
    token.value = '';
    label.value = '';
    userLabel.value = '';
    hostname.value = '';
    hostType.value = '';
    online.value = false;

    if (Get.isRegistered<GatewayStatusBusService>()) {
      GatewayStatusBusService.to.stopPolling();
    }

    if (!removePersisted) return;

    final uid = _currentUid();
    if (uid == null) return;

    _prefs ??= await SharedPreferences.getInstance();
    await _prefs!.remove(_sessionPrefsKey(uid));
  }

  Future<void> resetInMemory() async {
    await clearSession(removePersisted: false);
  }

  Future<void> _ensureGatewayAccess(String uid, String gatewayKey, String normalizedToken) async {
    final key = gatewayKey.trim();
    final token = normalizedToken.trim().toUpperCase();
    if (key.isEmpty || token.isEmpty) return;

    final accessRef = FirebaseDatabase.instance.ref('userGatewayAccess/$uid/$key');
    try {
      final snap = await accessRef.get();
      if (snap.exists) return;
      await accessRef.set({
        'token': token,
        'grantedAt': ServerValue.timestamp,
      });
    } catch (e) {
      _log(ConsoleLogType.system, 'PAIR', 'Gateway access grant failed: $e');
      rethrow;
    }
  }

  Future<void> _applySession(String key, String normalizedToken) async {
    gatewayKey.value = key;
    token.value = normalizedToken;
    await _startPresenceListener();
    await _refreshLabel();
    await _refreshUserLabel();
  }

  Future<void> saveGatewayLabel(String rawToken, String rawLabel) async {
    final uid = _currentUid();
    final normalized = rawToken.trim().toUpperCase();
    final trimmed = GatewayLabelUtils.clean(rawLabel);
    if (uid == null || normalized.isEmpty || trimmed.isEmpty) return;

    await FirebaseDatabase.instance.ref('userGatewayLabels/$uid/$normalized').set(trimmed);
    if (token.value == normalized) {
      userLabel.value = trimmed;
    }
    await _rememberInHistoryForToken(normalized, trimmed);
  }

  Future<void> _trySaveUserLabel(String normalizedToken, String rawLabel) async {
    final trimmed = GatewayLabelUtils.clean(rawLabel);
    if (trimmed.isEmpty) return;
    try {
      await saveGatewayLabel(normalizedToken, trimmed);
    } catch (e) {
      _log(ConsoleLogType.system, 'PAIR', 'Gateway label not saved: $e');
    }
  }

  Future<void> _rememberInHistoryForToken(String normalizedToken, String labelText) async {
    if (!Get.isRegistered<GatewayHistoryService>()) return;
    final entry = GatewayHistoryService.to.gateways.firstWhereOrNull((g) => g.token == normalizedToken);
    await GatewayHistoryService.to.remember(
      token: normalizedToken,
      gatewayKey: entry?.gatewayKey ?? gatewayKey.value,
      label: labelText,
    );
  }

  Future<void> _refreshUserLabel() async {
    final uid = _currentUid();
    final normalized = token.value;
    if (uid == null || normalized.isEmpty) {
      userLabel.value = '';
      return;
    }

    try {
      final snap = await FirebaseDatabase.instance.ref('userGatewayLabels/$uid/$normalized').get();
      userLabel.value = snap.exists ? snap.value.toString().trim() : '';
    } catch (_) {
      userLabel.value = '';
    }
  }

  Future<void> _persistSession(String uid) async {
    _prefs ??= await SharedPreferences.getInstance();
    await _prefs!.setString(
      _sessionPrefsKey(uid),
      jsonEncode({
        'gatewayKey': gatewayKey.value,
        'token': token.value,
      }),
    );
  }

  Future<void> _rememberInHistory() async {
    if (!Get.isRegistered<GatewayHistoryService>()) return;
    await GatewayHistoryService.to.remember(
      token: token.value,
      gatewayKey: gatewayKey.value,
      label: userLabel.value.isNotEmpty ? userLabel.value : label.value,
    );
  }

  Future<void> _migrateLegacySession(String uid) async {
    final legacyKey = (_prefs!.getString(AppConfig.prefsGatewayKey) ?? '').trim();
    final legacyToken = (_prefs!.getString(AppConfig.prefsGatewayToken) ?? '').trim().toUpperCase();
    if (legacyKey.isEmpty || legacyToken.isEmpty) return;

    final hasSession = _prefs!.getString(_sessionPrefsKey(uid)) != null;
    if (hasSession) {
      await _prefs!.remove(AppConfig.prefsGatewayKey);
      await _prefs!.remove(AppConfig.prefsGatewayToken);
      return;
    }

    await _prefs!.setString(
      _sessionPrefsKey(uid),
      jsonEncode({'gatewayKey': legacyKey, 'token': legacyToken}),
    );
    await _prefs!.remove(AppConfig.prefsGatewayKey);
    await _prefs!.remove(AppConfig.prefsGatewayToken);
  }

  Future<void> _refreshLabel() async {
    final key = gatewayKey.value;
    if (key.isEmpty) return;

    try {
      final configSnap = await FirebaseDatabase.instance.ref('gateways/$key/config').get();
      if (configSnap.exists && configSnap.value is Map) {
        final config = Map<String, dynamic>.from(configSnap.value as Map);
        label.value = (config['label'] ?? '').toString();
      }
    } catch (_) {
      label.value = '';
    }
  }

  Future<void> _startPresenceListener() async {
    final key = gatewayKey.value;
    if (key.isEmpty) return;

    await _presenceSub?.cancel();
    final ref = FirebaseDatabase.instance.ref('gateways/$key/presence');
    _presenceSub = ref.onValue.listen((event) {
      final value = event.snapshot.value;
      if (value is! Map) {
        online.value = false;
        hostType.value = '';
        return;
      }
      final presence = Map<String, dynamic>.from(value);
      online.value = presence['online'] == true;
      hostname.value = (presence['hostname'] ?? '').toString();
      hostType.value = (presence['hostType'] ?? '').toString();
    });
  }

  void _log(ConsoleLogType type, String tag, String message) {
    if (Get.isRegistered<ConsoleLogService>()) {
      ConsoleLogService.to.add(type: type, tag: tag, message: message);
    }
  }
}
