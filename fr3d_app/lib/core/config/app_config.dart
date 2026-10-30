/// Configuración global de la aplicación.
abstract final class AppConfig {
  static const String appName = 'MK3s+FR3D GATEWAY V2.0';

  /// Base 2.0.x — incrementar [appVersionPatch] y [uiReleaseDateTime] en cada deploy.
  static const String appVersionBase = '2.0';
  static const int appVersionPatch = 54;
  static String get appVersion => '$appVersionBase.$appVersionPatch';

    /// Material por defecto cuando no hay uno seleccionado (csv_logs/G.csv).
  static const String genericMaterialId = 'G';
  static const String uiProductTitle = 'MK3s+FR3D GATEWAY V2.0';
  static const String uiProductSubtitle = 'Cloud FR3D Gateway Remote Control for MK3S+';

  /// Fecha y hora del último release web (año-mes-día hora, zona local).
  static const String uiReleaseDateTime = '2026-09-09 17:05 PDT';

  static String get uiVersionLabel => 'Version $appVersion · $uiReleaseDateTime';

  /// Identificador visible del build web (cambia en cada deploy importante).
  static const String webBuildId = 'ui-2.0.54-copy-log-http-20260909';

  /// Ø digital (BDWIDTH/ARTME en Pi) con pestaña Extrusor visible.
  static const int piDiamFastPollMs = 1000;

  static const String uiPoweredBy = 'Powered by FR3D / Formake3d.com.ar';

  static const String firebaseDatabaseUrl = 'https://fr3d-3889a-default-rtdb.firebaseio.com';
  static const String firebaseProjectId = 'fr3d-3889a';

  /// Exclusive multi-device lock (last-write-wins at gateways/{key}/uiLock).
  static const bool enableGatewayExclusiveLock = true;

  static const int maxConsoleLines = 500;
  /// Timeout por defecto de comandos (s).
  static const int commandTimeoutSeconds = 20;
  /// Persistencia CSV tras corrida larga (copia G.csv puede ser pesada en Pi Zero).
  static const int csvFileSaveTimeoutSeconds = 90;
  /// Auto-resync del canal Flutter cuando hay timeout OFFLINE (también en standby).
  static const int channelResyncIntervalSeconds = 60;
  static const int statusPollSeconds = 15;
  static const int statusPollActiveSeconds = 10;
  /// Standby: no extrusion/winder active, cold machine, and not heating for a run.
  static const int statusPollStandbySeconds = 1800;
  static const int statusPollStandbyBarSegments = 10;
  /// Actual nozzle temp must be at or below this to allow standby (°C).
  static const int standbyActualTempMaxC = 99;
  /// Target temp above this = preparation for extrusion → never standby (°C).
  static const int standbyPrepTargetTempMaxC = 150;
  /// Tras actividad del operador, no entrar en standby hasta pasado este tiempo.
  static const int standbyUserActivityGraceMinutes = 3;
  static const int mk3AutoReconnectMinutes = 1;
  static const int statusCsvRows = 1;
  /// Max materiales en PImaterial.csv (LIST + CREATE en gateway).
  static const int materialCatalogMax = 20;
  /// Max colores en PIcolors.csv (LIST + CREATE en gateway).
  static const int colorCatalogMax = 40;
  /// Ultimas filas al cargar csv_logs/{id}.csv en Analisis (CSV FILE READ TAIL N).
  /// Mayor que el FIFO RAM (100) para que el histograma en vivo vea toda la corrida reciente.
  static const int csvFileReadTailMax = 2000;
  /// Corridas fechadas por material (`35.yyyymmddHHmmss`), anillo FIFO.
  /// El recorte lo aplica el gateway al guardar (CSV_HISTORY_MAX_PER_MATERIAL).
  static const int csvHistoryMaxPerMaterial = 20;
  static const int tokenLength = 8;

  /// Bootstrap superuser account (always superuser role).
  static const String superUserEmail = 'dadone.c@gmail.com';

  static const String prefsGatewayKey = 'fr3d_gateway_key';
  static const String prefsGatewayToken = 'fr3d_gateway_token';
  static const String prefsSessionPrefix = 'fr3d_session';
  static const String prefsGatewaysPrefix = 'fr3d_gateways';
}
