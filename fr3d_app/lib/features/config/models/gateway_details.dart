class GatewayDetails {
  const GatewayDetails({
    this.label = '',
    this.token = '',
    this.gatewayKey = '',
    this.hostname = '',
    this.hostType = '',
    this.mac = '',
    this.serial = '',
    this.mk3Port = '',
    this.lanIp = '',
    this.online = false,
    this.lastSeenMs = 0,
  });

  final String label;
  final String token;
  final String gatewayKey;
  final String hostname;
  final String hostType;
  final String mac;
  final String serial;
  final String mk3Port;
  final String lanIp;
  final bool online;
  final int lastSeenMs;

  bool get isWindowsHost => hostType.trim().toLowerCase() == 'windows';

  bool get isRaspberryPiHost =>
      hostType.trim().toLowerCase() == 'raspberry_pi';

  bool get isUnoQHost => hostType.trim().toLowerCase() == 'uno_q';

  /// Pi o Arduino UNO Q: OTA / UI LAN.
  bool get isLinuxGatewayHost => isRaspberryPiHost || isUnoQHost;

  /// Gateway Linux con IP LAN publicada (UI local en http://IP/).
  bool get canOpenLanUi {
    if (!isLinuxGatewayHost) return false;
    final ip = lanIp.trim();
    if (ip.isEmpty || ip == '0.0.0.0' || ip == '127.0.0.1') return false;
    final parts = ip.split('.');
    if (parts.length != 4) return false;
    return parts.every((p) {
      final n = int.tryParse(p);
      return n != null && n >= 0 && n <= 255;
    });
  }

  String get lanControlUrl => 'http://${lanIp.trim()}/';

  factory GatewayDetails.fromFirebase({
    required String gatewayKey,
    required String sessionToken,
    required String sessionLabel,
    required bool sessionOnline,
    required String sessionHostname,
    Map<String, dynamic>? config,
    Map<String, dynamic>? presence,
  }) {
    final cfg = config ?? {};
    final pres = presence ?? {};
    final configLabel = (cfg['label'] ?? '').toString().trim();
    final label = sessionLabel.trim().isNotEmpty ? sessionLabel.trim() : configLabel;
    final token = (cfg['token'] ?? sessionToken).toString().trim().toUpperCase();

    return GatewayDetails(
      gatewayKey: gatewayKey,
      label: label.isNotEmpty ? label : gatewayKey,
      token: token.isNotEmpty ? token : sessionToken,
      hostname: (pres['hostname'] ?? sessionHostname).toString(),
      hostType: (pres['hostType'] ?? '').toString(),
      mac: (pres['mac'] ?? '').toString(),
      serial: (pres['serial'] ?? '').toString(),
      mk3Port: (pres['mk3Port'] ?? '').toString(),
      lanIp: (pres['lanIp'] ?? '').toString().trim(),
      online: pres['online'] == true || sessionOnline,
      lastSeenMs: _asInt(pres['lastSeen']),
    );
  }

  static int _asInt(dynamic value) {
    if (value is int) return value;
    if (value is num) return value.toInt();
    return int.tryParse('$value') ?? 0;
  }
}
