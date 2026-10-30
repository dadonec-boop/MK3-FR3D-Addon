import 'package:get/get.dart';
import 'package:shared_preferences/shared_preferences.dart';

import '../config/app_config.dart';
import '../models/gateway_link_state.dart';
import '../models/user_role.dart';
import '../../features/analysis/models/csv_file_entry.dart';

class LanguageService extends GetxService {
  static LanguageService get to => Get.find<LanguageService>();

  static const _prefKey = 'login_language';
  static const supportedCodes = {'en', 'es', 'de'};

  final RxString code = 'en'.obs;

  @override
  void onInit() {
    super.onInit();
    _load();
  }

  Future<void> _load() async {
    final prefs = await SharedPreferences.getInstance();
    final saved = prefs.getString(_prefKey);
    if (saved != null && supportedCodes.contains(saved)) {
      code.value = saved;
    }
  }

  Future<void> setCode(String next) async {
    if (!supportedCodes.contains(next) || next == code.value) return;
    code.value = next;
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString(_prefKey, next);
  }

  bool get isEs => code.value == 'es';
  bool get isDe => code.value == 'de';

  String get help => isEs ? 'Ayuda' : isDe ? 'Hilfe' : 'Help';
  String get zoomIn => isEs ? 'Acercar' : isDe ? 'Vergrößern' : 'Zoom in';
  String get zoomOut => isEs ? 'Alejar' : isDe ? 'Verkleinern' : 'Zoom out';
  String get zoomReset => isEs ? 'Restablecer zoom' : isDe ? 'Zoom zurücksetzen' : 'Reset zoom';
  String get zoomHint => isEs
      ? 'Scroll = página normal. Clic en Scroll = último zoom de esta pestaña. Clic en % = volver a Scroll. −/+ ajustan el zoom (se guarda por pestaña).'
      : isDe
          ? 'Scroll = normale Seite. Klick auf Scroll = letzter Zoom dieses Tabs. Klick auf % = zurück zu Scroll. −/+ merken sich den Zoom pro Tab.'
          : 'Scroll = normal page. Click Scroll = last zoom for this tab. Click % = back to Scroll. −/+ save zoom per tab.';

  String get zoomScrollMode => isEs ? 'Scroll' : isDe ? 'Scroll' : 'Scroll';

  String get fitView => isEs ? 'Vista completa' : isDe ? 'Vollansicht' : 'Fit to screen';
  String get fitViewHint => isEs
      ? 'Modo vista completa (sin scroll vertical) para ver Extruder/Winder y el histograma en una sola vista.'
      : isDe
          ? 'Vollansichtsmodus (ohne vertikales Scrollen) für Extruder/Winder inkl. Histogramm in einer Ansicht.'
          : 'Full view mode (no vertical scrolling) to fit Extruder/Winder + histogram on screen.';
  String get tabs => isEs ? 'Pestañas' : isDe ? 'Tabs' : 'Tabs';
  String get about => isEs ? 'ACERCA DE' : isDe ? 'INFO' : 'ABOUT';
  String get signOut => isEs ? 'CERRAR SESIÓN' : isDe ? 'ABMELDEN' : 'SIGN OUT';
  String get email => isEs ? 'Correo electrónico' : isDe ? 'E-Mail' : 'Email';
  String get password => isEs ? 'Contraseña' : isDe ? 'Passwort' : 'Password';
  String get close => isEs ? 'Cerrar' : isDe ? 'Schließen' : 'Close';
  String get cancel => isEs ? 'Cancelar' : isDe ? 'Abbrechen' : 'Cancel';
  String get languageTitle => isEs ? 'Idioma' : isDe ? 'Sprache' : 'Language';
  String get languageEnglish => 'English';
  String get languageSpanish => 'Español';
  String get languageGerman => 'Deutsch';
  String get languageConfigHint => isEs
      ? 'Los cambios se aplican al instante en toda la app, sin cerrar sesión.'
      : isDe
          ? 'Änderungen gelten sofort in der gesamten App, ohne Abmeldung.'
          : 'Changes apply immediately across the app, without signing out.';
  String get loginSubtitle => isEs
      ? 'Inicie sesión para controlar su extrusor'
      : isDe
          ? 'Melden Sie sich an, um Ihren Extruder zu steuern'
          : 'Sign in to control your extruder';
  String get loginLanSubtitle => isEs
      ? 'Acceso local — misma red que la Raspberry Pi'
      : isDe
          ? 'Lokaler Zugriff — gleiches Netz wie der Raspberry Pi'
          : 'Local access — same network as the Raspberry Pi';
  String get loginLanHint => isEs
      ? 'Usuario y clave del panel de configuración (por defecto addonfr3d).'
      : isDe
          ? 'Benutzer und Passwort des Setup-Panels (Standard: addonfr3d).'
          : 'Setup-panel username and password (default addonfr3d).';
  String get loginLanUser => isEs ? 'Usuario' : isDe ? 'Benutzer' : 'Username';
  String get loginFirstTimeHint => isEs
      ? 'Primera vez: pulse "Primera vez — crear cuenta" abajo'
      : isDe
          ? 'Zum ersten Mal hier? Tippen Sie unten auf „Zum ersten Mal — Konto erstellen“'
          : 'First time: tap "First time — create account" below';
  String get loginFirstTimeGatewaySetup => isEs
      ? 'WIKI de la Familia del producto FR3dAddon'
      : isDe
          ? 'WIKI der FR3dAddon-Produktfamilie'
          : 'FR3dAddon product family WIKI';
  String get loginForgotPassword => isEs ? 'Olvidé mi contraseña' : isDe ? 'Passwort vergessen' : 'Forgot password';
  String get loginSignIn => isEs ? 'Iniciar sesión' : isDe ? 'Anmelden' : 'Sign in';
  String get loginCreateAccount => isEs ? 'Crear cuenta' : isDe ? 'Konto erstellen' : 'Create account';
  String get loginAlreadyHaveAccount =>
      isEs ? 'Ya tengo cuenta — iniciar sesión' : isDe ? 'Ich habe bereits ein Konto — anmelden' : 'Already have an account — sign in';
  String get loginFirstTimeCreateAccount =>
      isEs ? 'Primera vez — crear cuenta' : isDe ? 'Zum ersten Mal — Konto erstellen' : 'First time — create account';
  String get loginEmailSent => isEs ? 'Correo enviado' : isDe ? 'E-Mail gesendet' : 'Email sent';
  String get loginResetPassword => isEs ? 'Restablecer contraseña' : isDe ? 'Passwort zurücksetzen' : 'Reset password';
  String get loginResetSuccess => isEs
      ? 'Si existe una cuenta con ese correo, recibirá un enlace para restablecer la contraseña.\n\nRevise la bandeja de entrada y el correo no deseado.'
      : isDe
          ? 'Falls für diese E-Mail ein Konto existiert, erhalten Sie einen Link zum Zurücksetzen des Passworts.\n\nBitte prüfen Sie Ihren Posteingang und den Spam-Ordner.'
      : 'If an account exists for that email, you will receive a link to reset your password.\n\nCheck your inbox and spam folder.';
  String get loginResetInstructions => isEs
      ? 'Le enviaremos un enlace por correo para elegir una nueva contraseña.'
      : isDe
          ? 'Wir senden Ihnen per E-Mail einen Link, damit Sie ein neues Passwort wählen können.'
      : 'We will email you a link to choose a new password.';
  String get loginSendLink => isEs ? 'Enviar enlace' : isDe ? 'Link senden' : 'Send link';
  String get tabExtruder => isEs ? 'EXTRUSOR' : isDe ? 'EXTRUDER' : 'EXTRUDER';
  String get tabWinder => isEs ? 'BOBINADOR' : isDe ? 'WICKLER' : 'WINDER';
  String get tabLcd => isEs ? 'LCD' : isDe ? 'LCD' : 'LCD';
  String get tabAnalysis => isEs ? 'ANÁLISIS' : isDe ? 'ANALYSE' : 'ANALYSIS';
  String get tabConfig => isEs ? 'CONFIG' : isDe ? 'KONFIG' : 'CONFIG';
  String get tabConsole => isEs ? 'CONSOLA' : isDe ? 'KONSOLE' : 'CONSOLE';
  String get lcdHint => isEs
      ? 'Emulador del Smart Controller 2004. ◀/▶ giran; ● click. Mejor en LAN; en nube ~1–2 s por gesto.'
      : isDe
          ? 'Emulator des Smart Controllers 2004. ◀/▶ drehen; ● Klick. Am besten im LAN; Cloud ~1–2 s/Geste.'
          : 'Smart Controller 2004 emulator. ◀/▶ turn; ● click. Best on LAN; cloud ~1–2 s per gesture.';
  String get lcdHwEncoder => isEs
      ? 'Encoder físico'
      : isDe
          ? 'Physischer Encoder'
          : 'Physical encoder';
  String get lcdHwEncoderHint => isEs
      ? 'OFF en banco sin panel (pines flotantes). ON con Smart Controller conectado.'
      : isDe
          ? 'AUS ohne Panel (floating pins). EIN mit angeschlossenem Smart Controller.'
          : 'OFF on a bench without panel (floating pins). ON with Smart Controller connected.';
  String get lcdRefresh => isEs ? 'Actualizar LCD' : isDe ? 'LCD aktualisieren' : 'Refresh LCD';
  String get lcdDisplayConfigTitle => isEs
      ? 'Display / LCD'
      : isDe
          ? 'Display / LCD'
          : 'Display / LCD';
  String get account => isEs ? 'Cuenta' : isDe ? 'Konto' : 'Account';
  String get userId => isEs ? 'Id de usuario' : isDe ? 'Benutzer-ID' : 'User id';
  String get role => isEs ? 'Rol' : isDe ? 'Rolle' : 'Role';
  String get userProfiles => isEs ? 'PERFILES DE USUARIO' : isDe ? 'BENUTZERPROFILE' : 'USER PROFILES';
  String get userProfilesDialogTitle =>
      isEs ? 'Perfiles de usuario' : isDe ? 'Benutzerprofile' : 'User profiles';
  String get userProfilesIntro => isEs
      ? 'Asigne roles (operador / administrador / superusuario), envíe reset de contraseña o elimine un perfil.'
      : isDe
          ? 'Rollen zuweisen (Operator / Administrator / Superuser), Passwort-Reset senden oder Profil löschen.'
          : 'Assign roles (operator / administrator / superuser), send a password reset, or delete a profile.';
  String get noUserProfilesFound => isEs
      ? 'No se encontraron perfiles de usuario.'
      : isDe
          ? 'Keine Benutzerprofile gefunden.'
          : 'No user profiles found.';
  String get userPasswordResetTooltip => isEs
      ? 'Enviar enlace para cambiar contraseña'
      : isDe
          ? 'Link zum Passwortändern senden'
          : 'Send password reset link';
  String userPasswordResetSent(String email) => isEs
      ? 'Se envió un enlace de restablecimiento a $email.'
      : isDe
          ? 'Passwort-Reset-Link an $email gesendet.'
          : 'Password reset link sent to $email.';
  String get userErrNoEmailForReset => isEs
      ? 'Este perfil no tiene correo para restablecer la contraseña.'
      : isDe
          ? 'Dieses Profil hat keine E-Mail für den Passwort-Reset.'
          : 'This profile has no email for password reset.';
  String get save => isEs ? 'Guardar' : isDe ? 'Speichern' : 'Save';

  String roleLabel(UserRole role) => switch (role) {
        UserRole.operator => isEs ? 'Operador' : isDe ? 'Operator' : 'Operator',
        UserRole.administrator => isEs ? 'Administrador' : isDe ? 'Administrator' : 'Administrator',
        UserRole.superuser => isEs ? 'Superusuario' : isDe ? 'Superuser' : 'Superuser',
      };

  String get userErrOnlySuperusers => isEs
      ? 'Solo los superusuarios pueden gestionar perfiles.'
      : isDe
          ? 'Nur Superuser können Benutzerprofile verwalten.'
          : 'Only superusers can manage user profiles.';
  String get userErrSignInRequired => isEs
      ? 'Debe iniciar sesión.'
      : isDe
          ? 'Anmeldung erforderlich.'
          : 'Sign in required.';
  String userErrBootstrapMustRemainSuper(String email) => isEs
      ? '$email debe seguir siendo superusuario.'
      : isDe
          ? '$email muss Superuser bleiben.'
          : '$email must remain a superuser.';
  String get userErrCannotDeleteSelf => isEs
      ? 'No puede eliminar su propio perfil.'
      : isDe
          ? 'Eigenes Profil kann nicht gelöscht werden.'
          : 'You cannot delete your own profile.';
  String userErrCannotDeleteBootstrap(String email) => isEs
      ? 'No se puede eliminar el perfil de $email.'
      : isDe
          ? 'Profil von $email kann nicht gelöscht werden.'
          : 'Cannot delete the profile for $email.';
  String get userDeleteTooltip =>
      isEs ? 'Eliminar usuario' : isDe ? 'Benutzer löschen' : 'Delete user';
  String get userDeleteConfirmTitle =>
      isEs ? 'Eliminar usuario' : isDe ? 'Benutzer löschen' : 'Delete user';
  String userDeleteConfirmMessage(String email) => isEs
      ? '¿Eliminar el perfil de $email? El usuario podrá volver a iniciar sesión con rol operador.'
      : isDe
          ? 'Profil von $email löschen? Der Benutzer kann sich erneut als Operator anmelden.'
          : 'Delete profile for $email? The user can sign in again with the operator role.';

  String get aboutTabsWithConsole => isEs
      ? 'Use las pestañas EXTRUSOR, BOBINADOR, ANÁLISIS, LCD, CONFIG y CONSOLA.'
      : isDe
          ? 'Verwenden Sie die Tabs EXTRUDER, WICKLER, ANALYSE, LCD, KONFIG und KONSOLE.'
          : 'Use EXTRUDER, WINDER, ANALYSIS, LCD, CONFIG and CONSOLE tabs.';
  String get aboutTabsNoConsole => isEs
      ? 'Use las pestañas EXTRUSOR, BOBINADOR, ANÁLISIS, LCD y CONFIG.'
      : isDe
          ? 'Verwenden Sie die Tabs EXTRUDER, WICKLER, ANALYSE, LCD und KONFIG.'
          : 'Use EXTRUDER, WINDER, ANALYSIS, LCD and CONFIG tabs.';

  String get gatewayFallback => isEs ? 'gateway' : isDe ? 'Gateway' : 'gateway';
  String get activeGateway => isEs ? 'Gateway activo' : isDe ? 'Aktives Gateway' : 'Active gateway';
  String get lanIp => isEs ? 'IP LAN' : isDe ? 'LAN-IP' : 'LAN IP';
  String get openOnLan =>
      isEs ? 'Abrir en LAN' : isDe ? 'Im LAN öffnen' : 'Open on LAN';
  String get openLanFailed => isEs
      ? 'No se pudo abrir la UI local. Compruebe que está en la misma red WiFi.'
      : isDe
          ? 'Lokale UI konnte nicht geöffnet werden. Prüfen Sie, ob Sie im gleichen WLAN sind.'
          : 'Could not open the local UI. Check that you are on the same WiFi.';
  String get noGatewayPaired => isEs
      ? 'Sin gateway emparejado. Pulse el nombre del gateway en la barra de estado para conectar.'
      : isDe
          ? 'Kein Gateway gekoppelt. Tippen Sie in der Statusleiste auf den Gateway-Namen.'
          : 'No gateway paired. Tap the gateway name in the status bar to connect.';
  String get statusLabel => isEs ? 'Estado' : isDe ? 'Status' : 'Status';
  String get online => isEs ? 'EN LÍNEA' : isDe ? 'ONLINE' : 'ONLINE';
  String get offline => isEs ? 'FUERA DE LÍNEA' : isDe ? 'OFFLINE' : 'OFFLINE';
  String get gatewayOfflineCannotSend => isEs
      ? 'Gateway fuera de línea — no se pueden enviar comandos.'
      : isDe
          ? 'Gateway offline — Befehle gesperrt.'
          : 'Gateway offline — commands blocked until it is online.';
  String get gatewayControlLostTitle => isEs
      ? 'Otro dispositivo tiene el control'
      : isDe
          ? 'Ein anderes Gerät hat die Kontrolle'
          : 'Another device has control';
  String get gatewayControlLostBody => isEs
      ? 'Esta sesión quedó en solo lectura. Pulsá “Tomar el control” para operar esta Pi (el otro dispositivo se desconectará de la operación).'
      : isDe
          ? 'Diese Sitzung ist schreibgeschützt. Tippe auf „Kontrolle übernehmen“, um diese Pi zu bedienen (das andere Gerät verliert die Bedienung).'
          : 'This session is read-only. Press “Take control” to operate this Pi (the other device will lose operational control).';
  String gatewayControlLostBodyWithOwner(String owner) => isEs
      ? 'Control actual: $owner.\n\nEsta sesión quedó en solo lectura. Pulsá “Tomar el control” para operar esta Pi.'
      : isDe
          ? 'Aktuelle Kontrolle: $owner.\n\nDiese Sitzung ist schreibgeschützt. Tippe auf „Kontrolle übernehmen“.'
          : 'Current control: $owner.\n\nThis session is read-only. Press “Take control” to operate this Pi.';
  String get gatewayTakeControl =>
      isEs ? 'Tomar el control' : isDe ? 'Kontrolle übernehmen' : 'Take control';
  String get gatewayControlBlocked => isEs
      ? 'Otro dispositivo tiene el control de este gateway.'
      : isDe
          ? 'Ein anderes Gerät steuert dieses Gateway.'
          : 'Another device has control of this gateway.';
  String get name => isEs ? 'Nombre' : isDe ? 'Name' : 'Name';
  String get token => isEs ? 'Token' : isDe ? 'Token' : 'Token';
  String get gatewayKey => isEs ? 'Clave gateway' : isDe ? 'Gateway-Schlüssel' : 'Gateway key';
  String get hostname => isEs ? 'Hostname' : isDe ? 'Hostname' : 'Hostname';
  String get hostType => isEs ? 'Tipo de host' : isDe ? 'Host-Typ' : 'Host type';
  String get mac => 'MAC';
  String get serialPi => isEs ? 'Serial Pi' : isDe ? 'Pi-Seriennummer' : 'Serial Pi';
  String get serialComTitle =>
      isEs ? 'Puerto COM (Windows)' : isDe ? 'COM-Port (Windows)' : 'COM port (Windows)';
  String get serialComHint => isEs
      ? 'Solo en gateway Windows. Elegí el COM del MK3 y aplicá (reconecta solo).'
      : isDe
          ? 'Nur bei Windows-Gateway. COM des MK3 wählen und anwenden (verbindet neu).'
          : 'Windows gateway only. Pick the MK3 COM port and apply (reconnects).';
  String get serialComWindowsOnly => isEs
      ? 'Este panel solo aplica cuando el gateway corre en Windows.'
      : isDe
          ? 'Dieses Panel gilt nur, wenn das Gateway unter Windows läuft.'
          : 'This panel applies only when the gateway runs on Windows.';
  String get serialComActive =>
      isEs ? 'Puerto activo' : isDe ? 'Aktiver Port' : 'Active port';
  String get serialComPort => isEs ? 'Puerto COM' : isDe ? 'COM-Port' : 'COM port';
  String get serialComManual => isEs
      ? 'COM manual (opcional)'
      : isDe
          ? 'COM manuell (optional)'
          : 'Manual COM (optional)';
  String get serialComApply =>
      isEs ? 'APLICAR COM' : isDe ? 'COM ANWENDEN' : 'APPLY COM';
  String get serialComEmptyPort => isEs
      ? 'Indicá un puerto COM (p. ej. COM6).'
      : isDe
          ? 'Geben Sie einen COM-Port an (z. B. COM6).'
          : 'Enter a COM port (e.g. COM6).';
  String get lastSeen => isEs ? 'Última vez' : isDe ? 'Zuletzt gesehen' : 'Last seen';
  String get refresh => isEs ? 'ACTUALIZAR' : isDe ? 'AKTUALISIEREN' : 'REFRESH';
  String get changeGateway => isEs ? 'CAMBIAR GATEWAY' : isDe ? 'GATEWAY WECHSELN' : 'CHANGE GATEWAY';
  String get changeGatewayDialogTitle =>
      isEs ? 'Cambiar gateway' : isDe ? 'Gateway wechseln' : 'Change gateway';
  String get changeGatewaySubtitle => isEs
      ? 'Seleccione un gateway guardado o ingrese un token nuevo.'
      : isDe
          ? 'Gespeichertes Gateway wählen oder neuen Token eingeben.'
          : 'Select a saved gateway or enter a new token.';
  String get savedGateways =>
      isEs ? 'Gateways guardados' : isDe ? 'Gespeicherte Gateways' : 'Saved gateways';
  String get currentGateway => isEs ? 'ACTUAL' : isDe ? 'AKTUELL' : 'CURRENT';
  String get renameGateway =>
      isEs ? 'Renombrar gateway' : isDe ? 'Gateway umbenennen' : 'Rename gateway';
  String get gatewayNameLabel =>
      isEs ? 'Nombre del gateway' : isDe ? 'Gateway-Name' : 'Gateway name';
  String get enterGatewayName => isEs
      ? 'Ingrese un nombre para el gateway.'
      : isDe
          ? 'Geben Sie einen Gateway-Namen ein.'
          : 'Enter a gateway name.';
  String get removeFromList =>
      isEs ? 'Quitar de la lista' : isDe ? 'Aus Liste entfernen' : 'Remove from list';
  String removeGatewayConfirm(String label, String token) => isEs
      ? '$label ($token) se quitará de sus gateways guardados.'
      : isDe
          ? '$label ($token) wird aus Ihren gespeicherten Gateways entfernt.'
          : '$label ($token) will be removed from your saved gateways.';
  String get enterToken => isEs ? 'Ingresar token' : isDe ? 'Token eingeben' : 'Enter token';
  String get addAnotherGateway => isEs
      ? 'Agregar otro gateway'
      : isDe
          ? 'Weiteres Gateway hinzufügen'
          : 'Add another gateway';
  String get gatewayTokenLabel =>
      isEs ? 'Token del gateway' : isDe ? 'Gateway-Token' : 'Gateway token';
  String get newToken => isEs ? 'Token nuevo' : isDe ? 'Neuer Token' : 'New token';
  String get gatewayNameOptional => isEs
      ? 'Nombre del gateway (opcional)'
      : isDe
          ? 'Gateway-Name (optional)'
          : 'Gateway name (optional)';
  String get connectNew =>
      isEs ? 'Conectar nuevo' : isDe ? 'Neu verbinden' : 'Connect new';
  String get connectAction =>
      isEs ? 'Conectar' : isDe ? 'Verbinden' : 'Connect';
  String get backToList =>
      isEs ? 'Volver a la lista' : isDe ? 'Zurück zur Liste' : 'Back to list';

  String get gatewayErrAlreadyUsingToken => isEs
      ? 'Ya está usando ese token.'
      : isDe
          ? 'Dieser Token wird bereits verwendet.'
          : 'Already using that token.';
  String get gatewayErrSignInBeforePairing => isEs
      ? 'Inicie sesión antes de emparejar.'
      : isDe
          ? 'Melden Sie sich vor dem Koppeln an.'
          : 'Sign in before pairing.';
  String gatewayErrTokenLength(int length) => isEs
      ? 'El token debe tener $length caracteres.'
      : isDe
          ? 'Der Token muss $length Zeichen haben.'
          : 'Token must be $length characters.';
  String get gatewayErrTokenNotFound => isEs
      ? 'Token no encontrado. Verifique el código en la pantalla del MK3.'
      : isDe
          ? 'Token nicht gefunden. Code auf dem MK3-Display prüfen.'
          : 'Token not found. Check the code on the MK3 display.';
  String get gatewayErrTokenNoGateway => isEs
      ? 'El token no tiene gateway asociado en Firebase.'
      : isDe
          ? 'Token hat kein zugeordnetes Gateway in Firebase.'
          : 'Token has no associated gateway in Firebase.';

  String get chooseGateway => isEs ? 'Elegir gateway' : isDe ? 'Gateway wählen' : 'Choose gateway';
  String pairingEnterToken(int length) => isEs
      ? 'Ingrese el token de $length caracteres'
      : isDe
          ? 'Geben Sie den $length-stelligen Token ein'
          : 'Enter the $length-character token';
  String get pairingSelectOrAdd => isEs
      ? 'Seleccione un gateway o agregue uno nuevo'
      : isDe
          ? 'Gateway auswählen oder neues hinzufügen'
          : 'Select a gateway or add a new one';
  String get pairingTokenHint => isEs
      ? 'El token aparece en el LCD del MK3 (menú Control → addonfr3d-gateway). '
          'Sus gateways se guardan para esta cuenta.'
      : isDe
          ? 'Der Token erscheint auf dem MK3-LCD (Menü Steuerung → addonfr3d-gateway). '
              'Ihre Gateways werden für dieses Konto gespeichert.'
          : 'The token appears on the MK3 LCD (menu Control → addonfr3d-gateway). '
              'Your gateways are saved for this account.';
  String get pairingFirstTimeSetup => isEs
      ? 'WIKI de la Familia del producto FR3dAddon'
      : isDe
          ? 'WIKI der FR3dAddon-Produktfamilie'
          : 'FR3dAddon product family WIKI';
  String get pairingBackToLogin => isEs
      ? 'Volver al inicio de sesión'
      : isDe
          ? 'Zurück zur Anmeldung'
          : 'Back to sign in';

  String get pollStandby => 'STANDBY';
  String pollStandbyPolling() =>
      isEs ? 'Standby — consultando gateway...' : isDe ? 'Standby — Gateway wird abgefragt...' : 'Standby — polling gateway...';
  String pollStandbyNext(int minutes) => isEs
      ? 'Standby — próximo poll en $minutes min'
      : isDe
          ? 'Standby — nächster Poll in $minutes Min.'
          : 'Standby — next poll in $minutes min';
  String pollPolling() => isEs
      ? 'Consultando gateway (STATUS / CSV / WINDER)...'
      : isDe
          ? 'Gateway wird abgefragt (STATUS / CSV / WINDER)...'
          : 'Polling gateway (STATUS / CSV / WINDER)...';
  String pollNextSeconds(int seconds) => isEs
      ? 'Próximo poll en ${seconds}s'
      : isDe
          ? 'Nächster Poll in ${seconds}s'
          : 'Next poll in ${seconds}s';
  String get pollRefreshStandby => isEs
      ? 'Actualizar ahora (salir del ciclo standby)'
      : isDe
          ? 'Jetzt aktualisieren (Standby-Zyklus beenden)'
          : 'Refresh now (exit standby cycle)';
  String get pollRefreshNow => isEs
      ? 'Actualizar ahora (reiniciar temporizador)'
      : isDe
          ? 'Jetzt aktualisieren (Timer zurücksetzen)'
          : 'Refresh now (reset timer)';
  String get pollInProgress => isEs
      ? 'Poll en curso...'
      : isDe
          ? 'Abfrage läuft...'
          : 'Polling in progress...';

  String linkStateLabel(GatewayLinkState state) => switch (state) {
        GatewayLinkState.noGateway => isEs
            ? 'SIN GATEWAY'
            : isDe
                ? 'KEIN GATEWAY'
                : 'NO GATEWAY',
        GatewayLinkState.mk3Connected => isEs
            ? 'MK3S conectada'
            : isDe
                ? 'MK3S verbunden'
                : 'MK3S connected',
        GatewayLinkState.gatewayOffline => isEs
            ? 'Gateway FUERA DE LÍNEA'
            : isDe
                ? 'Gateway OFFLINE'
                : 'Gateway OFFLINE',
        GatewayLinkState.mk3Disconnected => isEs
            ? 'MK3S desconectada'
            : isDe
                ? 'MK3S getrennt'
                : 'MK3S disconnected',
        GatewayLinkState.cloudOffline => isEs
            ? 'Nube FUERA DE LÍNEA'
            : isDe
                ? 'Cloud OFFLINE'
                : 'Cloud OFFLINE',
      };

  String get apply => isEs ? 'APLICAR' : isDe ? 'ÜBERNEHMEN' : 'APPLY';
  String get assign => isEs ? 'ASIGNAR' : isDe ? 'ZUWEISEN' : 'ASSIGN';
  String get connect => isEs ? 'CONECTAR' : isDe ? 'VERBINDEN' : 'CONNECT';
  String get remove => isEs ? 'QUITAR' : isDe ? 'ENTFERNEN' : 'REMOVE';
  String get measure => isEs ? 'MEDIR' : isDe ? 'MESSEN' : 'MEASURE';
  String get measuring => isEs ? 'MIDIENDO…' : isDe ? 'MESSUNG…' : 'MEASURING…';
  String get rescan => isEs ? 'REESCANEAR' : isDe ? 'NEU SCANNEN' : 'RESCAN';
  String get saved => isEs ? 'Guardado' : isDe ? 'Gespeichert' : 'Saved';
  String get measured => isEs ? 'Medido' : isDe ? 'Gemessen' : 'Measured';
  String get parameter => isEs ? 'Parámetro' : isDe ? 'Parameter' : 'Parameter';

  String get wifiTitle =>
      isEs ? 'WiFi (gateway Raspberry Pi)' : isDe ? 'WiFi (Raspberry-Pi-Gateway)' : 'WiFi (Raspberry Pi gateway)';
  String get wifiPairFirst => isEs
      ? 'Empareje un gateway primero. Vea Ayuda → Configuración inicial del gateway.'
      : isDe
          ? 'Koppeln Sie zuerst ein Gateway. Siehe Hilfe → Ersteinrichtung des Gateways.'
          : 'Pair a gateway first. See Help → First-time gateway setup.';
  String get wifiPiOnly => isEs
      ? 'La gestión WiFi solo está disponible en gateways Raspberry Pi.'
      : isDe
          ? 'WiFi-Verwaltung ist nur auf Raspberry-Pi-Gateways verfügbar.'
          : 'WiFi management is only available on Raspberry Pi gateways.';
  String wifiFactoryHint(String ssid) => isEs
      ? 'Las imágenes de fábrica incluyen hotspot $ssid / $ssid. '
          'Tras el primer emparejamiento puede añadir aquí el WiFi del sitio.'
      : isDe
          ? 'Werksimages liefern Hotspot $ssid / $ssid. '
              'Nach der ersten Kopplung können Sie hier Ihr Standort-WLAN hinzufügen.'
          : 'Factory images ship with hotspot $ssid / $ssid. '
              'After first pairing you can add your site WiFi here.';
  String get wifiNew => isEs ? 'WiFi nuevo' : isDe ? 'Neues WLAN' : 'New WiFi';
  String get wifiSsid => 'SSID';
  String get wifiScanning => isEs ? 'ESCANEANDO…' : isDe ? 'SCANNE…' : 'SCANNING…';
  String get wifiAvailable => isEs ? 'DISPONIBLES' : isDe ? 'VERFÜGBAR' : 'AVAILABLE';
  String get wifiPasswordHelper =>
      isEs ? 'Use - para redes abiertas' : isDe ? '„-“ für offene Netzwerke' : 'Use - for open networks';
  String get wifiSavedNetworks =>
      isEs ? 'Redes guardadas' : isDe ? 'Gespeicherte Netzwerke' : 'Saved networks';
  String get wifiNoSavedProfiles => isEs
      ? 'Aún no hay perfiles guardados.'
      : isDe
          ? 'Noch keine gespeicherten Profile.'
          : 'No saved profiles yet.';
  String get wifiAvailableTitle =>
      isEs ? 'WiFi disponible' : isDe ? 'Verfügbares WLAN' : 'Available WiFi';
  String get wifiNoNetworksFound => isEs
      ? 'No se encontraron redes. Acerque el router e intente de nuevo.'
      : isDe
          ? 'Keine Netzwerke gefunden. Näher an den Router gehen und erneut versuchen.'
          : 'No networks found. Move closer to the router and try again.';
  String get wifiConnectedLabel =>
      isEs ? 'WiFi conectado:' : isDe ? 'WLAN verbunden:' : 'WiFi connected:';
  String get wifiNotConnected =>
      isEs ? '(sin conexión)' : isDe ? '(nicht verbunden)' : '(not connected)';
  String get wifiFactoryTag => isEs ? '(fábrica)' : isDe ? '(Werk)' : '(factory)';

  String get hallTitle => isEs
      ? 'Selección y configuración de sensor de diámetro'
      : isDe
          ? 'Durchmessersensor-Auswahl und -Konfiguration'
          : 'Diameter sensor selection and configuration';
  String get hallIntro => isEs
      ? 'Coloque un patrón de calibración bajo el sensor de diámetro, pulse MEDIR y luego APLICAR '
          'el ADC medido a la fila correspondiente. El offset (DOFF) corrige el error sistemático de diámetro.\n'
          'El sensor de diámetro puede ser de efecto Hall (montaje tipo INFIDEL) o óptico (basado en ARTME 3D). '
          'Para cableado A3, filtros EMI y montaje vea Ayuda → Hardware del sensor de diámetro. '
          'La misma calibración está en el LCD del MK3 — Ayuda → A) Standalone MK3S.'
      : isDe
          ? 'Legen Sie ein Kalibriermuster unter den Durchmessersensor, tippen Sie MESSEN und dann ÜBERNEHMEN '
              'für den gemessenen ADC in der passenden Zeile. Offset (DOFF) korrigiert systematischen Durchmesserfehler.\n'
              'Der Durchmessersensor kann Hall-Effekt (INFIDEL-Montage) oder optisch (ARTME 3D) sein. '
              'Für A3-Verkabelung, EMI-Filter und Montage siehe Hilfe → Durchmesser-Sensor-Hardware. '
              'Gleiche Kalibrierung am MK3-LCD — Hilfe → A) Standalone MK3S.'
          : 'Place a calibration pattern under the diameter sensor, tap MEASURE, then APPLY '
              'the measured ADC to the matching row. Offset (DOFF) corrects systematic diameter error.\n'
              'The diameter sensor may be Hall-effect (INFIDEL-style assembly) or optical (ARTME 3D based). '
              'For A3 wiring, EMI filters, and assembly see Help → Diameter sensor hardware. '
              'Same calibration is available on the MK3 LCD — Help → A) Standalone MK3S.';
  String get hallMk3NotReady => isEs
      ? 'MK3 no lista — conecte y espere el bootstrap.'
      : isDe
          ? 'MK3 nicht bereit — verbinden und Bootstrap abwarten.'
          : 'MK3 not ready — connect and wait for bootstrap.';
  String hallPatternRow(double mm) {
    final shown = mm.toStringAsFixed(2).replaceFirst(RegExp(r'0$'), '').replaceFirst(RegExp(r'\.$'), '');
    return isEs
        ? 'Fila patrón $shown mm'
        : isDe
            ? 'Musterzeile $shown mm'
            : 'Pattern row $shown mm';
  }
  String get hallChangePatterns => isEs
      ? 'Pattern Diameter'
      : isDe
          ? 'Pattern Diameter'
          : 'Pattern Diameter';
  String get hallPatternPresetA => 'Set 1.5/1.7/2.0';
  String get hallPatternPresetB => 'Set 1.7/1.75/2.0';
  String hallPatternCurrent(String pat, String mmLabel) => isEs
      ? 'Now $mmLabel'
      : isDe
          ? 'Now $mmLabel'
          : 'Now $mmLabel';
  String get hallPatternChangeWarn => isEs
      ? 'Al cambiar el patrón se invalida la calibración y OFFSET (DOFF) vuelve a 0. Debe medir de nuevo las 3 filas.'
      : isDe
          ? 'Preset-Wechsel macht die Kalibrierung ungültig und setzt OFFSET (DOFF) auf 0. Alle 3 Zeilen neu messen.'
          : 'Changing the pattern invalidates calibration and sets OFFSET (DOFF) to 0. Re-measure all 3 rows.';
  String get hallNeedCalibBanner => isEs
      ? 'Need Calibrate! — complete las filas del patrón. El predictor no actúa hasta CALV=1.'
      : isDe
          ? 'Need Calibrate! — Musterzeilen abschließen. Prädiktor inaktiv bis CALV=1.'
          : 'Need Calibrate! — complete the pattern rows. Predictor inactive until CALV=1.';
  String get hallStatusCalibrated => isEs
      ? 'Estado: Calibrado (CALV=1)'
      : isDe
          ? 'Status: Kalibriert (CALV=1)'
          : 'Status: Calibrated (CALV=1)';
  String get hallStatusNotCalibrated => isEs
      ? 'Estado: No calibrado (CALV=0)'
      : isDe
          ? 'Status: Nicht kalibriert (CALV=0)'
          : 'Status: Not calibrated (CALV=0)';
  String get hallStatusUnknown => isEs
      ? 'Estado: desconocido (pulse Actualizar)'
      : isDe
          ? 'Status: unbekannt (Aktualisieren tippen)'
          : 'Status: unknown (tap Refresh)';
  String get hallStatusDhOn => isEs
      ? 'Sensor Hall: ON (DH=1)'
      : isDe
          ? 'Hall-Sensor: AN (DH=1)'
          : 'Hall sensor: ON (DH=1)';
  String get hallStatusDhOff => isEs
      ? 'Sensor Hall: OFF (DH=0) — LCD AO'
      : isDe
          ? 'Hall-Sensor: AUS (DH=0) — LCD AO'
          : 'Hall sensor: OFF (DH=0) — LCD AO';
  String get hallEnableDh => isEs
      ? 'Habilitar sensor Hall (DH=1)'
      : isDe
          ? 'Hall-Sensor aktivieren (DH=1)'
          : 'Enable Hall sensor (DH=1)';
  String get hallEnableDhHint => isEs
      ? 'CALV=1 pero el medidor está apagado (DH=0). El LCD pone AO (no AC). Activá DH sin recalibrar.'
      : isDe
          ? 'CALV=1, aber Sensor aus (DH=0). LCD zeigt AO (nicht AC). DH ohne Neu-Kalibrierung aktivieren.'
          : 'CALV=1 but sensor is off (DH=0). LCD shows AO (not AC). Enable DH without recalibrating.';
  String get hallEnableDhOk => isEs
      ? 'Sensor Hall habilitado (DH=1).'
      : isDe
          ? 'Hall-Sensor aktiv (DH=1).'
          : 'Hall sensor enabled (DH=1).';
  String get hallEnableDhFailed => isEs
      ? 'No se pudo poner DH=1. Revisá HALL STATUS.'
      : isDe
          ? 'DH=1 konnte nicht gesetzt werden. HALL STATUS prüfen.'
          : 'Could not set DH=1. Check HALL STATUS.';
  String get hallSavedVsMeasuredHint => isEs
      ? 'Guardado = calibración en EEPROM del MK3. Medido = lectura A3 en vivo (solo con MEDIR).'
      : isDe
          ? 'Gespeichert = EEPROM-Kalibrierung am MK3. Gemessen = Live-A3 (nur mit MESSEN).'
          : 'Saved = MK3 EEPROM calibration. Measured = live A3 (only while MEASURE is on).';
  String get hallActivateSavedCal => isEs
      ? 'Activar calibración guardada'
      : isDe
          ? 'Gespeicherte Kalibrierung aktivieren'
          : 'Activate saved calibration';
  String get hallActivateSavedHint => isEs
      ? 'Hay puntos ADC guardados pero CALV=0 (p. ej. tras un flash). Reactiva el flag sin remedir.'
      : isDe
          ? '3 ADC-Punkte gespeichert, aber CALV=0 (z. B. nach Flash). Flag ohne Neu-Messung setzen.'
          : '3 ADC points are saved but CALV=0 (e.g. after a flash). Re-enable the flag without re-measuring.';
  String get hallActivateSavedOk => isEs
      ? 'Calibración guardada activada (CALV=1).'
      : isDe
          ? 'Gespeicherte Kalibrierung aktiv (CALV=1).'
          : 'Saved calibration activated (CALV=1).';
  String get hallActivateSavedFailed => isEs
      ? 'No se pudo activar CALV=1. Revisá HALL STATUS / puntos guardados.'
      : isDe
          ? 'CALV=1 konnte nicht gesetzt werden. HALL STATUS / Punkte prüfen.'
          : 'Could not set CALV=1. Check HALL STATUS / saved points.';
  String get hallActivateSavedUnavailable => isEs
      ? 'No hay puntos guardados válidos para reactivar.'
      : isDe
          ? 'Keine 3 gültigen gespeicherten Punkte zum Aktivieren.'
          : 'No valid saved 3-point set to activate.';
  String get predBlockedNoHallCal => isEs
      ? 'No puede corregir: calibrá el medidor de diámetro (CALV=0).'
      : isDe
          ? 'Keine Korrektur: Durchmessersensor kalibrieren (CALV=0).'
          : 'Cannot correct: calibrate the diameter sensor (CALV=0).';
  String get predBlockedHallOff => isEs
      ? 'No puede corregir: sensor Hall apagado (DH=0).'
      : isDe
          ? 'Keine Korrektur: Hall-Sensor aus (DH=0).'
          : 'Cannot correct: Hall sensor off (DH=0).';
  String get predGoEnableHall => isEs
      ? 'Ir a habilitar Hall'
      : isDe
          ? 'Hall aktivieren'
          : 'Go enable Hall';
  String get predGoCalibrate => isEs
      ? 'Ir a calibrar'
      : isDe
          ? 'Zur Kalibrierung'
          : 'Go to calibrate';
  String get predDiamManualLabel =>
      isEs ? 'Ø ingreso manual' : isDe ? 'Ø manuelle Eingabe' : 'Ø manual entry';
  String get predDiamManualThin =>
      isEs ? 'fino' : isDe ? 'dünn' : 'thin';
  String get predDiamManualThick =>
      isEs ? 'grueso' : isDe ? 'dick' : 'thick';
  String get predDiamBarReadOnly =>
      isEs ? 'solo lectura' : isDe ? 'nur Anzeige' : 'read only';
  String get predDiamBarAnalogLabel => isEs
      ? 'Ø sensor analógico A3'
      : isDe
          ? 'Ø Analog-Sensor A3'
          : 'Ø analog sensor A3';
  String get predDiamBarDigitalLabel => isEs
      ? 'Ø sensor Digital (gateway)'
      : isDe
          ? 'Ø Digital (Gateway)-Sensor'
          : 'Ø Digital (gateway) sensor';
  String get predDiamManualBarHint => isEs
      ? 'Tocá o arrastrá: izquierda = fino (1,20 mm), centro = Ø target del predictor, derecha = grueso (hasta 2,80 mm).'
      : isDe
          ? 'Tippen/ziehen: links = dünn (1,20 mm), Mitte = Predictor-Ø-Ziel, rechts = dick (bis 2,80 mm).'
          : 'Tap or drag: left = thin (1.20 mm), center = predictor Ø target, right = thick (up to 2.80 mm).';
  String get predDiamBarLiveHint => isEs
      ? 'Barra de solo lectura: muestra el Ø vivo (A3 o Digital gateway) respecto al objetivo.'
      : isDe
          ? 'Nur-Anzeige: zeigt den Live-Ø (A3 oder Digital Gateway) relativ zum Ziel.'
          : 'Read-only bar: shows live Ø (A3 or Digital gateway) relative to the target.';
  String get predDiamManualHint => isEs
      ? 'Solo con fuente Manual. Barra táctil: 1,20 / Ø target / 2,80 mm. '
          'El MK3 usa este Ø fijo (sin sensor). Dejá Auto=ON para que el predictor corrija con ese valor.'
      : isDe
          ? 'Nur bei Quelle Manuell. Touch-Leiste: 1,20 / Ø-Ziel / 2,80 mm. '
              'MK3 nutzt diesen festen Ø (ohne Sensor). Auto=EIN, damit der Prädiktor damit arbeitet.'
          : 'Only with Manual source. Touch bar: 1.20 / Ø target / 2.80 mm. '
              'MK3 uses this fixed Ø (no sensor). Leave Auto=ON so the predictor acts on that value.';
  String get predDiamManualSend =>
      isEs ? 'Enviar' : isDe ? 'Senden' : 'Send';
  String get predDiamManualInvalid => isEs
      ? 'Ø inválido. Usá un número entre 1,20 y 2,80 mm.'
      : isDe
          ? 'Ungültiger Ø. Zahl zwischen 1,20 und 2,80 mm.'
          : 'Invalid Ø. Use a number between 1.20 and 2.80 mm.';
  String get predMk3IdleNoDelta => isEs
      ? 'Auto ON: el MK3 no aplicó ΔE/ΔT este ciclo (hold / settle / gate). El LCD debe mostrar AH, AS, AG o AB — no solo A.'
      : isDe
          ? 'Auto EIN: MK3 hat dieses Zyklus kein ΔE/ΔT (Hold/Settle/Gate). LCD sollte AH/AS/AG/AB zeigen.'
          : 'Auto ON: MK3 did not apply ΔE/ΔT this cycle (hold / settle / gate). LCD should show AH, AS, AG or AB — not just A.';
  String get hallPatternSetOk => isEs
      ? 'Nuevo patrón OK. Need Calibrate! — mida las 3 filas.'
      : isDe
          ? 'Neues Preset OK. Need Calibrate! — 3 Zeilen messen.'
          : 'New setting OK. Need Calibrate! — measure all 3 rows.';
  String get hallOffsetDoff =>
      isEs ? 'Offset mm (DOFF)' : isDe ? 'Offset mm (DOFF)' : 'Offset mm (DOFF)';
  String get hallFootnote => isEs
      ? 'Aplicar en filas de patrón envía la lectura A3 en vivo al MK3 y guarda EEPROM (MS). '
          'La medición se detiene sola tras 3 minutos. Guardado ≠ Medido: Medido solo aparece con MEDIR.'
      : isDe
          ? 'Übernehmen bei Musterzeilen sendet den live A3-ADC an den MK3 und speichert EEPROM (MS). '
              'Messung stoppt automatisch nach 3 Minuten. Gespeichert ≠ Gemessen: Gemessen nur mit MESSEN.'
          : 'Apply on pattern rows sends the live A3 ADC reading to the MK3 and saves EEPROM (MS). '
              'Measurement auto-stops after 3 minutes. Saved ≠ Measured: Measured only shows while MEASURE is on.';

  String get gatewayTimeout => isEs
      ? 'El gateway no respondió a tiempo. La Pi puede estar ocupada o fuera de línea.'
      : isDe
          ? 'Gateway hat nicht rechtzeitig geantwortet. Der Pi ist evtl. beschäftigt oder offline.'
          : 'Gateway did not respond in time. The Pi may be busy or offline.';

  String get wifiErrPiRequired => isEs
      ? 'Los comandos WiFi requieren un gateway Raspberry Pi.'
      : isDe
          ? 'WiFi-Befehle erfordern ein Raspberry-Pi-Gateway.'
          : 'WiFi commands require a Raspberry Pi gateway.';
  String get wifiErrScanPiRequired => isEs
      ? 'El escaneo WiFi requiere un gateway Raspberry Pi.'
      : isDe
          ? 'WiFi-Scan erfordert ein Raspberry-Pi-Gateway.'
          : 'WiFi scan requires a Raspberry Pi gateway.';
  String get wifiErrNoVisibleNetworks => isEs
      ? 'No se encontraron redes visibles. Intente más cerca del router.'
      : isDe
          ? 'Keine sichtbaren Netzwerke. Näher an den Router gehen und erneut versuchen.'
          : 'No visible networks found. Try again closer to the router.';
  String get wifiErrSsidRequired => isEs
      ? 'Ingrese un SSID o elija uno de las redes disponibles.'
      : isDe
          ? 'SSID eingeben oder aus verfügbaren Netzwerken wählen.'
          : 'Enter an SSID or pick one from available networks.';
  String get wifiErrPasswordRequired => isEs
      ? 'Ingrese la contraseña WiFi (use - para redes abiertas).'
      : isDe
          ? 'WLAN-Passwort eingeben („-“ für offene Netzwerke).'
          : 'Enter the WiFi password (use - for open networks).';
  String get wifiErrSavedNotConnected => isEs
      ? 'Perfil guardado pero aún sin conexión. Use CONECTAR en la lista o verifique la contraseña.'
      : isDe
          ? 'Profil gespeichert, aber noch nicht verbunden. VERBINDEN in der Liste oder Passwort prüfen.'
          : 'Profile saved but not connected yet. Try CONNECT on the saved list or check the password.';
  String wifiErrFactoryCannotRemove(String ssid) => isEs
      ? 'El perfil de fábrica $ssid no se puede eliminar.'
      : isDe
          ? 'Das Werkprofil $ssid kann nicht entfernt werden.'
          : 'The factory profile $ssid cannot be removed.';

  String get hallErrMk3NotConnectedStartup => isEs
      ? 'MK3 no conectada. Espere el arranque seguro.'
      : isDe
          ? 'MK3 nicht verbunden. Warten Sie auf sicheren Start.'
          : 'MK3 not connected. Wait for safe startup.';
  String get hallErrNoMeasured => isEs
      ? 'Sin valor medido. Pulse MEDIR primero.'
      : isDe
          ? 'Kein Messwert. Zuerst MESSEN tippen.'
          : 'No measured value. Tap MEASURE first.';
  String get hallErrInvalidOffset => isEs
      ? 'Valor de offset inválido.'
      : isDe
          ? 'Ungültiger Offset-Wert.'
          : 'Invalid offset value.';
  String hallErrOffsetRange(double min, double max) => isEs
      ? 'El offset debe estar entre $min y $max mm.'
      : isDe
          ? 'Offset muss zwischen $min und $max mm liegen.'
          : 'Offset must be between $min and $max mm.';
  String get hallErrMk3NotConnected => isEs
      ? 'MK3 no conectada.'
      : isDe
          ? 'MK3 nicht verbunden.'
          : 'MK3 not connected.';
  String get hallUsbCalDisabled => isEs
      ? 'Digital (gateway): el Ø llega por BDWidth USB o ARTME ADS1115 en un gateway Raspberry Pi 3B (no Pi Zero 2 W). ADC A3 y calibración Hall deshabilitados.'
      : isDe
          ? 'Digital (Gateway): Ø kommt vom BDWidth-USB oder ARTME ADS1115 an einem Raspberry-Pi-3B-Gateway (nicht Pi Zero 2 W). A3-ADC und Hall-Kalibrierung aus.'
          : 'Digital (gateway): Ø comes from BDWidth USB or ARTME ADS1115 on a Raspberry Pi 3B gateway (not Pi Zero 2 W). A3 ADC and Hall calibration off.';
  String get hallManualCalDisabled => isEs
      ? 'Manual: informe el Ø en la barra del predictor (EXTRUSOR). Con Auto ON ajusta T/RPM; a los 70 s sin nuevo valor asume PREDTGT (AR). Mida ~cada 60 s fuera de objetivo, ~cada 5 min si ya lo logró.'
      : isDe
          ? 'Manuell: Ø in der Prädiktor-Leiste (EXTRUDER). Bei Auto EIN: T/RPM; nach 70 s ohne Wert → PREDTGT (AR). Messen ~alle 60 s off-target, ~alle 5 min on-target.'
          : 'Manual: enter Ø on the predictor bar (EXTRUDER). With Auto ON it adjusts T/RPM; after 70 s without a new value assumes PREDTGT (AR). Measure ~every 60 s off-target, ~every 5 min on-target.';
  String get hallSensorSource =>
      isEs ? 'Fuente del sensor' : isDe ? 'Sensorquelle' : 'Sensor source';
  String get hallSourceModesExplain => isEs
      ? 'Elija una sola fuente (excluyente):\n'
          '• Analog A3 — Hall u óptico en pin A3 del MK3. Calibre con Pattern / MEDIR / APLICAR. '
          'Funciona standalone, con Pi Zero 2 W o Pi 3B.\n'
          '• Digital (gateway) — en Pi 3B: subtipo BDWidth USB o ARTME ADS1115 (cal 6 puntos en la Pi). Sin Hall A3.\n'
          '• Manual (mock) — informe Ø en la barra del predictor (EXTRUSOR) o LCD (D mm). Con Auto ON: ajusta T/RPM; a 70 s sin valor asume PREDTGT (AR). Mida ~60 s fuera de objetivo, ~5 min si ya lo logró.'
      : isDe
          ? 'Genau eine Quelle wählen (exklusiv):\n'
              '• Analog A3 — Hall/Optik an MK3-Pin A3. Mit Pattern / MESSEN / ÜBERNEHMEN kalibrieren. '
              'Standalone, Pi Zero 2 W oder Pi 3B.\n'
              '• Digital (Gateway) — am Pi 3B: Untertyp BDWidth USB oder ARTME ADS1115 (6-Punkt-Kal. auf der Pi). Kein Hall A3.\n'
              '• Manuell (Mock) — Ø in der Prädiktor-Leiste (EXTRUDER) oder LCD (D mm). Bei Auto EIN: T/RPM; nach 70 s ohne Wert → PREDTGT (AR). Messen ~60 s off-target, ~5 min on-target.'
          : 'Choose one source only (exclusive):\n'
              '• Analog A3 — Hall or optical on MK3 pin A3. Calibrate with Pattern / MEASURE / APPLY. '
              'Works standalone, Pi Zero 2 W, or Pi 3B.\n'
              '• Digital (gateway) — on Pi 3B: subtype BDWidth USB or ARTME ADS1115 (6-point cal on the Pi). No Hall A3.\n'
              '• Manual (mock) — enter Ø on the predictor bar (EXTRUDER) or LCD (D mm). With Auto ON: adjusts T/RPM; after 70 s without a value assumes PREDTGT (AR). Measure ~60 s off-target, ~5 min on-target.';
  String get hallDigitalBackendLabel => isEs
      ? 'Subtipo Digital'
      : isDe
          ? 'Digital-Untertyp'
          : 'Digital subtype';
  String get hallDigitalBdwidth => 'BDWidth USB';
  String get hallDigitalArtme => 'ARTME ADS1115';
  String get hallDigitalBackendExplain => isEs
      ? 'BDWidth: Ø digital por USB. ARTME: sensor óptico analógico vía ADS1115 I2C (calibración 6 puntos en la Pi, misma UX que A3).'
      : isDe
          ? 'BDWidth: digitaler Ø per USB. ARTME: optischer Analogsensor über ADS1115 I2C (6-Punkt-Kal. auf der Pi, wie A3).'
          : 'BDWidth: digital Ø over USB. ARTME: optical analog via ADS1115 I2C (6-point cal on the Pi, same UX as A3).';
  String get hallArtmeIntro => isEs
      ? 'ARTME 3D óptico en Pi 3B (ADS1115). MEDIR captura raw; APLICAR en 1.50…2.00 mm; luego activar calibración (CALV).'
      : isDe
          ? 'ARTME 3D Optik am Pi 3B (ADS1115). MESSEN speichert Raw; ÜBERNEHMEN bei 1.50…2.00 mm; dann Kalibrierung aktivieren (CALV).'
          : 'ARTME 3D optical on Pi 3B (ADS1115). MEASURE captures raw; APPLY at 1.50…2.00 mm; then activate calibration (CALV).';
  String get hallArtmeLiveLabel => isEs
      ? 'Ø / raw (ARTME)'
      : isDe
          ? 'Ø / Raw (ARTME)'
          : 'Ø / raw (ARTME)';
  String get hallArtmeCalValid =>
      isEs ? 'Calibración Pi' : isDe ? 'Pi-Kalibrierung' : 'Pi calibration';
  String get hallArtmeDisabled => isEs
      ? 'ARTME deshabilitado en gateway'
      : isDe
          ? 'ARTME am Gateway aus'
          : 'ARTME disabled on gateway';
  String get hallSourceA3 => isEs ? 'Analog A3' : isDe ? 'Analog A3' : 'Analog A3';
  String get hallSourceUsb =>
      isEs ? 'Digital (gateway)' : isDe ? 'Digital (Gateway)' : 'Digital (gateway)';
  String get hallSourceManual =>
      isEs ? 'Manual (mock)' : isDe ? 'Manuell (Mock)' : 'Manual (mock)';
  String get hallSourceChangeNeedsMk3 => isEs
      ? 'Los botones de arriba cambian la fuente activa en el MK3 (requiere conexión).'
      : isDe
          ? 'Die Schaltflächen oben wechseln die aktive Quelle am MK3 (Verbindung nötig).'
          : 'The buttons above change the active source on the MK3 (connection required).';
  String hallActiveSourceConfirmed(String name) => isEs
      ? 'Fuente activa en MK3: $name'
      : isDe
          ? 'Aktive Quelle am MK3: $name'
          : 'Active source on MK3: $name';
  String get hallActiveSourceChangeHint => isEs
      ? 'Cámbiela con los tres botones de arriba (Analog A3 / Digital gateway / Manual). La tarjeta con borde verde y etiqueta ACTIVA es la que usa el MK3 ahora.'
      : isDe
          ? 'Wechseln mit den drei Schaltflächen oben. Die Karte mit grünem Rand und ACTIVA ist die aktuelle MK3-Quelle.'
          : 'Change it with the three buttons above. The card with a green border and ACTIVE label is what the MK3 uses now.';
  String get hallActiveSourceUnknown => isEs
      ? 'Fuente activa en MK3: desconocida'
      : isDe
          ? 'Aktive Quelle am MK3: unbekannt'
          : 'Active source on MK3: unknown';
  String get hallActiveSourceUnknownHint => isEs
      ? 'Conecte el MK3 y espere el bootstrap. Luego pulse ACTUALIZAR en Analog A3 — el banner mostrará la fuente real (DIAMSRC). Para cambiarla use los botones de arriba.'
      : isDe
          ? 'MK3 verbinden und Bootstrap abwarten. Dann in Analog A3 AKTUALISIEREN — Banner zeigt DIAMSRC. Quelle wechseln mit den Schaltflächen oben.'
          : 'Connect the MK3 and wait for bootstrap. Then tap REFRESH in Analog A3 — the banner will show DIAMSRC. Change source with the buttons above.';
  String get hallActiveSourceUnknownLegacyHint => isEs
      ? 'Conecte el MK3. Este firmware solo soporta Analog A3. Tras ACTUALIZAR en Analog A3 verá la fuente confirmada.'
      : isDe
          ? 'MK3 verbinden. Diese Firmware unterstützt nur Analog A3. Nach AKTUALISIEREN in Analog A3 erscheint die bestätigte Quelle.'
          : 'Connect the MK3. This firmware only supports Analog A3. After REFRESH in Analog A3 you will see the confirmed source.';
  String get hallSubCardActive =>
      isEs ? 'ACTIVA' : isDe ? 'AKTIV' : 'ACTIVE';
  String get hallSubCardLegacyOnly => isEs
      ? 'Requiere firmware MK3 con DIAMSRC'
      : isDe
          ? 'Erfordert MK3-Firmware mit DIAMSRC'
          : 'Requires MK3 firmware with DIAMSRC';
  String get hallGatewayIntroOnDemand => isEs
      ? 'Medidor BDWidth en gateway Pi 3B (solo lectura). Pulse ACTUALIZAR para leer el Ø — no hay actualización automática.'
      : isDe
          ? 'BDWidth-Messgerät am Pi-3B-Gateway (nur Anzeige). AKTUALISIEREN tippen für Ø — keine Auto-Aktualisierung.'
          : 'BDWidth meter on Pi 3B gateway (read only). Tap REFRESH for Ø — no automatic updates.';
  String get hallGatewayTapRefresh => isEs
      ? 'Pulse ACTUALIZAR para leer Ø'
      : isDe
          ? 'AKTUALISIEREN tippen für Ø'
          : 'Tap REFRESH to read Ø';
  String get hallGatewayPreviewHint => isEs
      ? 'Vista previa (solo lectura). La fuente activa sigue siendo la seleccionada arriba.'
      : isDe
          ? 'Vorschau (nur Anzeige). Aktive Quelle bleibt die oben gewählte.'
          : 'Preview (read only). Active source remains the one selected above.';
  String get hallSubCardPreview =>
      isEs ? 'vista previa' : isDe ? 'Vorschau' : 'preview';
  String get hallGatewayLiveLabel =>
      isEs ? 'Ø vivo (gateway)' : isDe ? 'Live-Ø (Gateway)' : 'Live Ø (gateway)';
  String hallGatewayLive(String d) => isEs
      ? 'Ø vivo: $d'
      : isDe
          ? 'Live-Ø: $d'
          : 'Live Ø: $d';
  String get hallGatewayDisabled => isEs
      ? 'BDWidth deshabilitado en gateway'
      : isDe
          ? 'BDWidth am Gateway aus'
          : 'BDWidth disabled on gateway';
  String get hallGatewayConnectedNoD => isEs
      ? 'Conectado, sin lectura Ø'
      : isDe
          ? 'Verbunden, kein Ø'
          : 'Connected, no Ø reading';
  String get hallGatewayNotConnected => isEs
      ? 'Sensor no conectado'
      : isDe
          ? 'Sensor nicht verbunden'
          : 'Sensor not connected';
  String get hallGatewayEnabled =>
      isEs ? 'Habilitado' : isDe ? 'Aktiv' : 'Enabled';
  String get hallGatewayConnected =>
      isEs ? 'Conectado' : isDe ? 'Verbunden' : 'Connected';
  String get hallGatewayMode => isEs ? 'Modo' : isDe ? 'Modus' : 'Mode';
  String get hallGatewayPort => isEs ? 'Puerto' : isDe ? 'Port' : 'Port';
  String get hallGatewayVersion =>
      isEs ? 'Versión' : isDe ? 'Version' : 'Version';
  String get hallGatewayRaw => isEs ? 'Raw W' : isDe ? 'Raw W' : 'Raw W';
  String get hallGatewayAge => isEs ? 'Edad muestra' : isDe ? 'Sample-Alter' : 'Sample age';
  String get hallGatewayInjectMk3 =>
      isEs ? 'Inyectar MK3' : isDe ? 'MK3 injizieren' : 'Inject MK3';
  String get hallGatewayMk3Hostd =>
      isEs ? 'HOSTD (MK3)' : isDe ? 'HOSTD (MK3)' : 'HOSTD (MK3)';
  String get hallGatewayOn => isEs ? 'ON' : isDe ? 'EIN' : 'ON';
  String get hallGatewayOff => isEs ? 'OFF' : isDe ? 'AUS' : 'OFF';
  String get hallGatewayYes => isEs ? 'Sí' : isDe ? 'Ja' : 'Yes';
  String get hallGatewayNo => isEs ? 'No' : isDe ? 'Nein' : 'No';
  String get hallManualCurrentFixed =>
      isEs ? 'Ø fijo actual' : isDe ? 'Aktueller Fix-Ø' : 'Current fixed Ø';
  String hallManualFixed(String mm) => isEs
      ? 'Ø fijo: $mm mm'
      : isDe
          ? 'Fix-Ø: $mm mm'
          : 'Fixed Ø: $mm mm';
  String get hallManualNoValue => isEs
      ? 'Sin Ø informado'
      : isDe
          ? 'Kein Ø eingegeben'
          : 'No Ø entered';
  String get hallManualUsePredictor => isEs
      ? 'Informe el Ø en EXTRUSOR → barra del predictor (“Ø ingreso manual”). Cambiar a Manual requiere MK3 conectada.'
      : isDe
          ? 'Ø unter EXTRUDER → Prädiktor-Leiste eingeben. Wechsel zu Manuell erfordert verbundenes MK3.'
          : 'Enter Ø on EXTRUDER → predictor bar (“Ø manual entry”). Switching to Manual requires a connected MK3.';
  String get hallSourceLegacyOnly => isEs
      ? 'Solo Analog A3 (este MK3 no soporta Digital gateway / Manual). Actualice el firmware para esas fuentes.'
      : isDe
          ? 'Nur Analog A3 (dieses MK3 unterstützt kein Digital Gateway / Manuell). Firmware aktualisieren für diese Quellen.'
          : 'Analog A3 only (this MK3 has no Digital gateway / Manual). Update firmware for those sources.';

  String get mk3FwLegacyTitle => isEs
      ? 'Firmware MK3S+ desactualizado'
      : isDe
          ? 'MK3S+-Firmware veraltet'
          : 'MK3S+ firmware outdated';

  String get mk3FwLegacyBody => isEs
      ? 'Para usar las últimas funciones de la app (fuentes USB/Manual, calibración 6 puntos, Optimizar, etc.) '
          'debe actualizar el firmware del MK3S+.\n\n'
          'Puede descargar el paquete Arduino desde GitHub o continuar con la versión antigua '
          '(la app se adapta a este firmware).'
      : isDe
          ? 'Für die neuesten App-Funktionen (USB/Manuell, 6-Punkt-Kalibrierung, Optimieren usw.) '
              'muss die MK3S+-Firmware aktualisiert werden.\n\n'
              'Laden Sie das Arduino-Paket von GitHub herunter oder fahren Sie mit der alten Version fort '
              '(die App passt sich an).'
          : 'To use the latest app features (USB/Manual sources, 6-point calibration, Optimize, etc.) '
              'update the MK3S+ firmware.\n\n'
              'Download the Arduino package from GitHub, or continue with the old version '
              '(the app will match this firmware).';

  String get mk3FwLegacyDownload => isEs
      ? 'Descargar firmware'
      : isDe
          ? 'Firmware laden'
          : 'Download firmware';

  String get mk3FwLegacyContinue => isEs
      ? 'Continuar con versión antigua'
      : isDe
          ? 'Mit alter Version fortfahren'
          : 'Continue with old version';

  String get mk3FwLegacyBanner => isEs
      ? 'Firmware MK3S+ antiguo: algunas funciones de la app no están disponibles. Actualice el firmware desde GitHub.'
      : isDe
          ? 'Alte MK3S+-Firmware: einige App-Funktionen fehlen. Firmware von GitHub aktualisieren.'
          : 'Older MK3S+ firmware: some app features are unavailable. Update firmware from GitHub.';

  // —— UI común ——
  String get edit => isEs ? 'EDITAR' : isDe ? 'BEARBEITEN' : 'EDIT';
  String get clear => isEs ? 'LIMPIAR' : isDe ? 'LEEREN' : 'CLEAR';
  String get record => isEs ? 'GRABAR' : isDe ? 'AUFZEICHNEN' : 'RECORD';
  String get stop => isEs ? 'DETENER' : isDe ? 'STOPP' : 'STOP';
  String get start => isEs ? 'INICIAR' : isDe ? 'START' : 'START';
  String get starting => isEs ? 'INICIANDO…' : isDe ? 'STARTET…' : 'STARTING…';
  String get stopping => isEs ? 'DETENIENDO…' : isDe ? 'STOPPT…' : 'STOPPING…';
  String get pullDisabledNeedRun => isEs
      ? 'TRACCIÓN deshabilitada: requiere extrusión activa (botón en DETENER).'
      : isDe
          ? 'TRAKTION gesperrt: aktive Extrusion nötig (Schaltfläche STOPP).'
          : 'Pull disabled: requires active extrusion (button on STOP).';
  String get continueAction => isEs ? 'CONTINUAR' : isDe ? 'WEITER' : 'CONTINUE';
  String get pause => isEs ? 'PAUSA' : isDe ? 'PAUSE' : 'PAUSE';
  String get offset => 'OFFSET';
  String get applying => isEs ? 'APLICANDO…' : isDe ? 'WIRD ÜBERNOMMEN…' : 'APPLYING…';
  String get confirm => isEs ? 'Confirmar' : isDe ? 'Bestätigen' : 'Confirm';

  String get gatewayUpdateTitle => isEs
      ? 'Actualización del gateway'
      : isDe
          ? 'Gateway-Update'
          : 'Gateway update';
  String gatewayUpdatePiBody(String local, String remote) => isEs
      ? 'Hay una versión nueva del gateway ($local → $remote). ¿Actualizar ahora? El equipo se reiniciará unos segundos.'
      : isDe
          ? 'Neue Gateway-Version ($local → $remote). Jetzt aktualisieren? Das Gerät startet kurz neu.'
          : 'A newer gateway version is available ($local → $remote). Update now? The host will restart briefly.';
  String gatewayUpdateWindowsBody(String local, String remote) => isEs
      ? 'Hay una versión nueva del gateway Windows ($local → $remote). ¿Descargar el zip ahora?'
      : isDe
          ? 'Neue Windows-Gateway-Version ($local → $remote). Zip jetzt herunterladen?'
          : 'A newer Windows gateway version is available ($local → $remote). Download the zip now?';
  String get gatewayUpdateYes => isEs ? 'Sí' : isDe ? 'Ja' : 'Yes';
  String get gatewayUpdateNo => isEs ? 'No' : isDe ? 'Nein' : 'No';
  String get gatewayUpdateStarted => isEs
      ? 'Actualización iniciada. El gateway se reiniciará. Espere alrededor de un minuto y vuelva a entrar si hace falta.'
      : isDe
          ? 'Update gestartet. Das Gateway startet neu. Etwa eine Minute warten und bei Bedarf neu verbinden.'
          : 'Update started. The gateway will restart. Wait about a minute and reconnect if needed.';
  String get gatewayUpdateWindowsHowto => isEs
      ? 'Cierre FR3DGateway.exe, descargue el zip, descomprímalo encima de la carpeta (conserve config_gateway.csv) y vuelva a iniciar.'
      : isDe
          ? 'FR3DGateway.exe schließen, Zip laden, über den Ordner entpacken (config_gateway.csv behalten) und neu starten.'
          : 'Close FR3DGateway.exe, download the zip, unzip over the folder (keep config_gateway.csv), then start again.';
  String get gatewayUpdateDownload =>
      isEs ? 'Descargar zip' : isDe ? 'Zip laden' : 'Download zip';

  String get webUiUpdateTitle => isEs
      ? 'Actualización de interfaz LAN'
      : isDe
          ? 'LAN-Oberflächen-Update'
          : 'LAN UI update';

  String webUiUpdateBody(String local, String remote) => isEs
      ? 'Hay una interfaz nueva para la Pi (LAN).\nLocal: $local\nRemota: $remote\n¿Actualizar fr3d_web ahora?'
      : isDe
          ? 'Neue LAN-Oberfläche für die Pi.\nLokal: $local\nRemote: $remote\nJetzt fr3d_web aktualisieren?'
          : 'A new LAN UI is available for the Pi.\nLocal: $local\nRemote: $remote\nUpdate fr3d_web now?';

  String get webUiUpdateStarted => isEs
      ? 'Actualización de UI iniciada. Use PI UPDATE UI STATUS. Luego recargue http://IP-Pi/ .'
      : isDe
          ? 'UI-Update gestartet. PI UPDATE UI STATUS prüfen. Dann http://IP-Pi/ neu laden.'
          : 'UI update started. Use PI UPDATE UI STATUS. Then reload http://IP-Pi/ .';

  String get create => isEs ? 'CREAR' : isDe ? 'ERSTELLEN' : 'CREATE';
  String get update => isEs ? 'ACTUALIZAR' : isDe ? 'AKTUALISIEREN' : 'UPDATE';
  String get delete => isEs ? 'ELIMINAR' : isDe ? 'LÖSCHEN' : 'DELETE';
  String get add => isEs ? 'AGREGAR' : isDe ? 'HINZUFÜGEN' : 'ADD';
  String get loading => isEs ? 'Cargando…' : isDe ? 'Laden…' : 'Loading…';
  String get histogram => isEs ? 'Histograma' : isDe ? 'Histogramm' : 'Histogram';
  String get material => isEs ? 'Material' : isDe ? 'Material' : 'Material';
  String get materialGenericLabel =>
      isEs ? 'G — Genérico' : isDe ? 'G — Generisch' : 'G — Generic';
  String get selectMaterial =>
      isEs ? 'Seleccionar material' : isDe ? 'Material wählen' : 'Select material';
  String get loadingCatalog =>
      isEs ? 'Cargando catálogo…' : isDe ? 'Katalog wird geladen…' : 'Loading catalog…';
  String get noMaterials =>
      isEs ? 'Sin materiales' : isDe ? 'Keine Materialien' : 'No materials';
  String get gatewayBusy =>
      isEs ? 'Gateway ocupado; intente ACTUALIZAR.' : isDe ? 'Gateway beschäftigt; AKTUALISIEREN versuchen.' : 'Gateway busy; try REFRESH.';
  String get gatewayBusyMoment => isEs
      ? 'Gateway ocupado; intente ACTUALIZAR en un momento.'
      : isDe
          ? 'Gateway beschäftigt; gleich AKTUALISIEREN versuchen.'
          : 'Gateway busy; try REFRESH in a moment.';
  String get gatewayBusyWait => isEs
      ? 'Gateway ocupado — espere unos segundos (puede haber poll automático STATUS/CSV).'
      : isDe
          ? 'Gateway beschäftigt — kurz warten (automatischer STATUS/CSV-Poll möglich).'
          : 'Gateway busy — wait a few seconds and try again (automatic STATUS/CSV may be running).';
  String get operatorsCannotRunSoPi => cannotRunOsCriticalCommands;

  String get cannotRunOsCriticalCommands => isEs
      ? 'No puede ejecutar comandos SO ni PI (críticos para el sistema operativo).'
      : isDe
          ? 'SO- und PI-Befehle sind nicht erlaubt (kritisch für das Betriebssystem).'
          : 'SO and PI commands are not allowed (critical for the operating system).';

  String get operatorConsoleButtonsOnly => isEs
      ? 'Operador: solo botones de la consola (sin texto libre).'
      : isDe
          ? 'Operator: nur Konsolen-Chips (kein Freitext).'
          : 'Operator: console chips only (no free text).';
  String get extruderWaitingPoll => isEs
      ? 'Esperando poll del gateway (STATUS / CSV / WINDER)...'
      : isDe
          ? 'Warte auf Gateway-Poll (STATUS / CSV / WINDER)...'
          : 'Waiting for gateway poll (STATUS / CSV / WINDER)...';

  // —— Extrusor ——
  String get extruderControls => isEs ? 'Controles' : isDe ? 'Steuerung' : 'Controls';
  String get extruderSetpoints =>
      isEs ? 'Consignas (R / T / F / P)' : isDe ? 'Sollwerte (R / T / F / P)' : 'Setpoints (R / T / F / P)';
  String get extruderLiveStatus =>
      isEs ? 'Estado en vivo' : isDe ? 'Live-Status' : 'Live status';
  String get startExtruder => isEs ? 'INICIAR EXTRUSOR' : isDe ? 'EXTRUDER STARTEN' : 'START EXTRUDER';
  String get stopExtruder => isEs ? 'DETENER EXTRUSOR' : isDe ? 'EXTRUDER STOPPEN' : 'STOP EXTRUDER';
  String get pullAuto => 'PULL=Auto';
  String get pullManual => 'PULL=Manual';
  String get pullApplyingManual => 'PULL=Manual…';
  String get pullApplyingAutomatic => 'PULL=Auto…';
  String get cooldown => isEs ? 'ENFRIAR' : isDe ? 'ABKÜHLEN' : 'COOLDOWN';
  String get cooling => isEs ? 'ENFRIANDO…' : isDe ? 'KÜHLT…' : 'COOLING…';
  String get preheat => isEs ? 'PRECALENTAR' : isDe ? 'VORHEIZEN' : 'PREHEAT';
  String get preheating =>
      isEs ? 'PRECALENTANDO…' : isDe ? 'VORHEIZT…' : 'PREHEATING…';
  String get opening => isEs ? 'ABRIENDO…' : isDe ? 'ÖFFNET…' : 'OPENING…';
  String get rActTgt => 'R act/tgt';
  String get tActTgt => 'T act/tgt';
  String get fActTgt => 'F act/tgt';
  String get pActTgt => 'P act/tgt';
  String setpointTgt(String axis) =>
      isEs ? '$axis consigna' : isDe ? '$axis Soll' : '$axis tgt';
  String get histogramRecordStop => isEs
      ? 'Detener grabación del perfil CSV del filamento'
      : isDe
          ? 'CSV-Filamentprofil-Aufzeichnung stoppen'
          : 'Stop recording the CSV filament profile';
  String get histogramRecordStart => isEs
      ? 'Grabar el perfil CSV del filamento desde ahora'
      : isDe
          ? 'CSV-Filamentprofil ab jetzt aufzeichnen'
          : 'Record the CSV filament profile from now on';
  String get histogramRecordNeedExtruder => isEs
      ? 'Inicie el extrusor para grabar el perfil CSV'
      : isDe
          ? 'Extruder starten, um CSV-Profil aufzuzeichnen'
          : 'Start the extruder to record the CSV profile';
  String get histogramRecordNeedWinder => isEs
      ? 'Inicie el bobinado para grabar el perfil CSV'
      : isDe
          ? 'Wickeln starten, um CSV-Profil aufzuzeichnen'
          : 'Start winding to record the CSV profile';
  String get predictiveAssistant =>
      isEs ? 'Asistente predictivo' : isDe ? 'Prädiktiver Assistent' : 'Predictive assistant';
  String get predLastCorrection =>
      isEs ? 'Última corrección' : isDe ? 'Letzte Korrektur' : 'Last correction';
  String get predNow => isEs ? 'Ahora' : isDe ? 'Jetzt' : 'Now';
  String get manualAutomatic =>
      isEs ? 'Manual / automático' : isDe ? 'Manuell / automatisch' : 'Manual / automatic';
  String get predictorParams =>
      isEs ? 'Parámetros del predictor' : isDe ? 'Prädiktor-Parameter' : 'Predictor parameters';
  String get predictorMk3NotReady => isEs
      ? 'Conecte el MK3 y espere el arranque seguro antes de editar límites del predictor.'
      : isDe
          ? 'MK3 verbinden und sicheren Start abwarten, bevor Prädiktor-Limits bearbeitet werden.'
          : 'Connect the MK3 and wait for safe startup before editing predictor limits.';
  String get viewRecommendations =>
      isEs ? 'Ver recomendaciones' : isDe ? 'Empfehlungen anzeigen' : 'View recommendations';
  String get editPredictorLimits =>
      isEs ? 'Editar límites del predictor' : isDe ? 'Prädiktor-Limits bearbeiten' : 'Edit predictor limits';
  String get predictorModeManual => isEs ? 'Manual' : isDe ? 'Manuell' : 'Manual';
  String get predictorModeAutomatic => isEs ? 'Automático' : isDe ? 'Automatisch' : 'Automatic';
  /// Botón predictor en panel (estados estables).
  String get predAutoOn => 'Auto=ON';
  String get predAutoOff => 'Auto=OFF';
  String get predOptOn => isEs ? 'Optimizar=ON' : isDe ? 'Optimize=EIN' : 'Optimize=ON';
  String get predOptOff => isEs ? 'Optimizar=OFF' : isDe ? 'Optimize=AUS' : 'Optimize=OFF';
  String get predPActLabel => isEs ? 'P act' : isDe ? 'P Ist' : 'P act';
  String get predPStarLabel => isEs ? 'P*' : isDe ? 'P*' : 'P*';
  String get predPStarHint => isEs
      ? 'P* vacío (—) = no busca eficiencia. Objetivo de tiraje con PULL en Auto: el MK3 mueve E y T; el primer +/− copia el P actual ±1.'
      : isDe
          ? 'P* leer (—) = keine Effizienzsuche. Ziel-Pull bei PULL=Auto: MK3 stellt E und T; erstes +/− kopiert Ist-P ±1.'
          : 'P* empty (—) = no efficiency seek. Pull target with PULL Auto: MK3 moves E and T; first +/− copies actual P ±1.';
  String get predPStarPlus => isEs ? 'Subir P*' : isDe ? 'P* hoch' : 'Raise P*';
  String get predPStarMinus => isEs ? 'Bajar P*' : isDe ? 'P* runter' : 'Lower P*';
  String get predOptNeedsGateway => isEs
      ? 'Optimizar requiere firmware MK3 actualizado (QUERY con PREDOPT) y gateway 2.2.0 o superior.'
      : isDe
          ? 'Optimize braucht aktuelle MK3-Firmware (QUERY mit PREDOPT) und Gateway 2.2.0 oder neuer.'
          : 'Optimize needs updated MK3 firmware (QUERY with PREDOPT) and gateway 2.2.0 or newer.';
  String get predApplyingOff => 'Auto=OFF…';
  String get predApplyingOn => 'Auto=ON…';
  String get predictorModeLabel => isEs ? 'Modo' : isDe ? 'Modus' : 'Mode';
  String get enableAssistant =>
      isEs ? 'Activar asistente' : isDe ? 'Assistent aktivieren' : 'Enable assistant';
  String get predictorProfileLabel => isEs ? 'Perfil' : isDe ? 'Profil' : 'Profile';
  String get profileConservative => isEs ? 'Conservador' : isDe ? 'Konservativ' : 'Conservative';
  String get profileBalanced => isEs ? 'Equilibrado' : isDe ? 'Ausgewogen' : 'Balanced';
  String get profileAggressive => isEs ? 'Agresivo' : isDe ? 'Aggressiv' : 'Aggressive';
  String get profileCustom => isEs ? 'Personalizado' : isDe ? 'Benutzerdefiniert' : 'Custom';
  String get saveProfile => isEs ? 'Guardar perfil' : isDe ? 'Profil speichern' : 'Save profile';
  String get superuserOnly =>
      isEs ? 'Solo superusuario' : isDe ? 'Nur Superuser' : 'Superuser only';
  String get loadingProfile =>
      isEs ? 'Cargando perfil…' : isDe ? 'Profil wird geladen…' : 'Loading profile...';
  String get predictorSectionBand =>
      isEs ? 'Límites banda R / T / D' : isDe ? 'R-/T-/D-Bandgrenzen' : 'R / T / D band limits';
  String get predictorSectionCycle =>
      isEs ? 'Ciclo / márgenes / filtro mediana' : isDe ? 'Zyklus / Margen / Medianfilter' : 'Cycle / margins / median filter';
  String get predictorSectionTarget =>
      isEs ? 'Objetivo / coincidencia térmica' : isDe ? 'Ziel / thermische Übereinstimmung' : 'Target / thermal match';
  String get predictorSectionDr =>
      isEs ? 'Pasos dR / ganancias R' : isDe ? 'dR-Schritte / R-Verstärkung' : 'dR steps / R gains';
  String get predictorSectionDt =>
      isEs ? 'Pasos dT / ganancias T' : isDe ? 'dT-Schritte / T-Verstärkung' : 'dT steps / T gains';
  String get predictorSaveHint => isEs
      ? 'Guardar almacena valores en Firebase globalmente (todos los tótems). '
          'Aplicar envía solo comandos PRED SET modificados al MK3.'
      : isDe
          ? 'Speichern schreibt global in Firebase (alle Totems). '
              'Übernehmen sendet nur geänderte PRED SET-Befehle an den MK3.'
          : 'Save stores values in Firebase globally (shared across all totems). '
              'Apply sends only changed PRED SET commands to the MK3.';
  String couldNotLoadProfile(String err) => isEs
      ? 'No se pudo cargar el perfil: $err'
      : isDe
          ? 'Profil konnte nicht geladen werden: $err'
          : 'Could not load profile: $err';
  String profileSavedGlobally(String name) => isEs
      ? 'Perfil "$name" guardado globalmente para todos los tótems.'
      : isDe
          ? 'Profil „$name“ global für alle Totems gespeichert.'
          : 'Profile "$name" saved globally for all totems.';
  String couldNotSaveProfile(String err) => isEs
      ? 'No se pudo guardar el perfil: $err'
      : isDe
          ? 'Profil konnte nicht gespeichert werden: $err'
          : 'Could not save profile: $err';
  String get materialTitle => isEs ? 'Material' : isDe ? 'Material' : 'Material';
  String materialSuggested(String r, String t, String f, String p) => isEs
      ? 'Sugerido: R $r · T $t · F $f · P $p'
      : isDe
          ? 'Vorschlag: R $r · T $t · F $f · P $p'
          : 'Suggested: R $r · T $t · F $f · P $p';
  String get errSelectMaterial =>
      isEs ? 'Seleccione un material.' : isDe ? 'Material wählen.' : 'Select a material.';
  String get errMaterialCatalogFull => isEs
      ? 'Limite de ${AppConfig.materialCatalogMax} materiales alcanzado.'
      : isDe
          ? 'Limit von ${AppConfig.materialCatalogMax} Materialien erreicht.'
          : 'Limit of ${AppConfig.materialCatalogMax} materials reached.';
  String get errColorCatalogFull => isEs
      ? 'Limite de ${AppConfig.colorCatalogMax} colores alcanzado.'
      : isDe
          ? 'Limit von ${AppConfig.colorCatalogMax} Farben erreicht.'
          : 'Limit of ${AppConfig.colorCatalogMax} colors reached.';
  String materialSaved(String id) => isEs
      ? 'Material $id guardado.'
      : isDe
          ? 'Material $id gespeichert.'
          : 'Material $id saved.';

  String get materialCatalog =>
      isEs ? 'Catálogo de materiales' : isDe ? 'Materialkatalog' : 'Material catalog';
  String get materialEditMaterial =>
      isEs ? 'Editar material' : isDe ? 'Material bearbeiten' : 'Edit material';
  String get materialEditColors =>
      isEs ? 'EDITAR COLORES' : isDe ? 'FARBEN BEARBEITEN' : 'EDIT COLORS';
  String get materialColorCatalog => isEs
      ? 'Catálogo de colores (PIcolors.csv)'
      : isDe
          ? 'Farbkatalog (PIcolors.csv)'
          : 'Color catalog (PIcolors.csv)';
  String get materialNewColorName =>
      isEs ? 'Nombre del color nuevo' : isDe ? 'Neuer Farbname' : 'New color name';
  String get materialAddColor =>
      isEs ? 'AGREGAR COLOR' : isDe ? 'FARBE HINZUFÜGEN' : 'ADD COLOR';
  String get materialNew => isEs ? 'NUEVO' : isDe ? 'NEU' : 'NEW';
  String get saving => isEs ? 'GUARDANDO…' : isDe ? 'SPEICHERN…' : 'SAVING...';

  String materialFieldLabel(String key) => switch (key) {
        'material' => isEs ? 'ID material' : isDe ? 'Material-ID' : 'Material ID',
        'type' => isEs ? 'Tipo' : isDe ? 'Typ' : 'Type',
        'origen_trit_en' => isEs ? 'Origen molido' : isDe ? 'Mahlgut-Herkunft' : 'Grind origin',
        'col_tritur_en' => isEs ? 'Color molido' : isDe ? 'Mahlgut-Farbe' : 'Grind color',
        'granulado_en' => isEs ? 'Tamaño gránulo' : isDe ? 'Granulatgröße' : 'Granule size',
        'sinfin_comp_en' => isEs ? 'Compresión tornillo' : isDe ? 'Schneckenkompression' : 'Worm compression',
        'rpm_suggest' => isEs ? 'RPM sugerido' : isDe ? 'RPM Vorschlag' : 'RPM suggest',
        'temp_suggest' => isEs ? 'Temp sugerida' : isDe ? 'Temp Vorschlag' : 'Temp suggest',
        'fan_suggest' => isEs ? 'Ventilador sugerido' : isDe ? 'Lüfter Vorschlag' : 'Fan suggest',
        'pull_rpm_suggest' =>
            isEs ? 'RPM tracción sugerido' : isDe ? 'Zug-RPM Vorschlag' : 'Pull RPM suggest',
        'pct_virgen' => isEs ? '% virgen' : isDe ? 'Jungmaterial %' : 'Virgin %',
        'pct_colorante' => isEs ? '% colorante' : isDe ? 'Farbstoff %' : 'Colorant %',
        'color_colorante' => isEs ? 'Color colorante' : isDe ? 'Farbstofffarbe' : 'Colorant color',
        'notas' => isEs ? 'Notas' : isDe ? 'Notizen' : 'Notes',
        'color_final' => isEs ? 'Color final' : isDe ? 'Endfarbe' : 'Final color',
        _ => key,
      };

  String materialSinfinLabel(String value) => switch (value.toUpperCase()) {
        'HIGH' => isEs ? 'ALTA' : isDe ? 'HOCH' : 'HIGH',
        'LOW' => isEs ? 'BAJA' : isDe ? 'NIEDRIG' : 'LOW',
        _ => value,
      };

  // —— Alertas de diámetro ——
  String get diameterVeryFineCritical =>
      isEs ? 'Muy fino — Crítico' : isDe ? 'Sehr dünn — Kritisch' : 'Very fine — Critical';
  String get diameterVeryFineWarning2 =>
      isEs ? 'Muy fino — Aviso 2' : isDe ? 'Sehr dünn — Warnung 2' : 'Very fine — Warning 2';
  String get diameterVeryFineWarning1 =>
      isEs ? 'Muy fino — Aviso 1' : isDe ? 'Sehr dünn — Warnung 1' : 'Very fine — Warning 1';
  String get diameterVeryCoarseCritical =>
      isEs ? 'Muy grueso — Crítico' : isDe ? 'Sehr dick — Kritisch' : 'Very thick — Critical';
  String get diameterVeryCoarseWarning2 =>
      isEs ? 'Muy grueso — Aviso 2' : isDe ? 'Sehr dick — Warnung 2' : 'Very thick — Warning 2';
  String get diameterVeryCoarseWarning1 =>
      isEs ? 'Muy grueso — Aviso 1' : isDe ? 'Sehr dick — Warnung 1' : 'Very thick — Warning 1';
  String get diameterAlertPopupFine => isEs
      ? 'Recomendaciones — filamento muy fino'
      : isDe
          ? 'Empfehlungen — Filament zu dünn'
          : 'Recommendations — filament too thin';
  String get diameterAlertPopupCoarse => isEs
      ? 'Recomendaciones — filamento muy grueso'
      : isDe
          ? 'Empfehlungen — Filament zu dick'
          : 'Recommendations — filament too thick';
  List<L10nStep> get diameterFineSteps => [
        L10nStep(
          title: isEs ? '1) Ventilador boquilla (F)' : isDe ? '1) Düsenlüfter (F)' : '1) Nozzle FAN',
          body: isEs
              ? 'Aumente manualmente la velocidad del ventilador (F) para que el filamento se estire menos bajo tensión antes de solidificarse.'
              : isDe
                  ? 'Düsenlüfter (F) manuell erhöhen, damit sich das Filament vor dem Erstarren weniger unter Spannung dehnt.'
                  : 'Manually increase nozzle fan speed (F) so the filament stretches less under tension before solidifying.',
        ),
        L10nStep(
          title: isEs ? '2) Ajuste mecánico de distancia' : isDe ? '2) Mechanische Abstandsanpassung' : '2) Mechanical distance adjustment',
          body: isEs
              ? 'Disminuya manualmente la distancia física del sensor (S), acercándolo a la boquilla para dar menos tiempo de estiramiento al plástico fundido.'
              : isDe
                  ? 'Physischen Sensorabstand (S) verringern — näher an die Düse — weniger Dehnzeit für geschmolzenes Material.'
                  : 'Manually decrease the physical sensor distance (S), moving it closer to the nozzle to give the molten plastic less stretch time.',
        ),
        L10nStep(
          title: isEs ? '3) Revisión física y calibración' : isDe ? '3) Physische Prüfung und Kalibrierung' : '3) Physical check and calibration',
          body: isEs
              ? 'Inspeccione desgaste interno de la boquilla. Verifique que el sensor de diámetro esté calibrado y no reporte lecturas falsas.'
              : isDe
                  ? 'Innere Düsenverschleiß prüfen. Durchmesser-Sensor kalibriert und ohne Fehlmessungen verifizieren.'
                  : 'Inspect internal wear of the nozzle orifice. Verify the diameter sensor is calibrated and not reporting false readings.',
        ),
        L10nStep(
          title: isEs ? '4) Ajuste de receta del lote' : isDe ? '4) Chargen-Rezeptanpassung' : '4) Batch recipe adjustment',
          body: isEs
              ? 'Disminuya el porcentaje de material reciclado (-T%) y aumente el virgen (+V%) para reducir la fluidez del fundido.'
              : isDe
                  ? 'Recycling-Anteil (-T%) senken und Jungmaterial (+V%) erhöhen, um Schmelzfließfähigkeit zu reduzieren.'
                  : 'Decrease recycled material percentage (-T%) and increase virgin material percentage (+V%) to reduce melt fluidity.',
        ),
      ];
  List<L10nStep> get diameterCoarseSteps => [
        L10nStep(
          title: isEs ? '1) Ventilador boquilla (F)' : isDe ? '1) Düsenlüfter (F)' : '1) Nozzle FAN',
          body: isEs
              ? 'Reduzca manualmente la velocidad del ventilador (F) para que el filamento pueda estirarse bajo tensión antes de solidificarse.'
              : isDe
                  ? 'Düsenlüfter (F) manuell reduzieren, damit sich das Filament vor dem Erstarren unter Spannung dehnen kann.'
                  : 'Manually reduce nozzle fan speed (F) so the filament can stretch under tension before solidifying.',
        ),
        L10nStep(
          title: isEs ? '2) Ajuste mecánico de distancia' : isDe ? '2) Mechanische Abstandsanpassung' : '2) Mechanical distance adjustment',
          body: isEs
              ? 'Aumente manualmente la distancia física del sensor (S), alejándolo de la boquilla para dar más tiempo de estiramiento al plástico fundido.'
              : isDe
                  ? 'Physischen Sensorabstand (S) vergrößern — weiter von der Düse — mehr Dehnzeit für geschmolzenes Material.'
                  : 'Manually increase the physical sensor distance (S), moving it away from the nozzle to give the molten plastic more stretch time.',
        ),
        L10nStep(
          title: isEs ? '3) Revisión física y calibración' : isDe ? '3) Physische Prüfung und Kalibrierung' : '3) Physical check and calibration',
          body: isEs
              ? 'Inspeccione desgaste interno de la boquilla. Verifique que el sensor de diámetro esté calibrado y no reporte lecturas falsas.'
              : isDe
                  ? 'Innere Düsenverschleiß prüfen. Durchmesser-Sensor kalibriert und ohne Fehlmessungen verifizieren.'
                  : 'Inspect internal wear of the nozzle orifice. Verify the diameter sensor is calibrated and not reporting false readings.',
        ),
        L10nStep(
          title: isEs ? '4) Ajuste de receta del lote' : isDe ? '4) Chargen-Rezeptanpassung' : '4) Batch recipe adjustment',
          body: isEs
              ? 'Aumente el porcentaje de material reciclado (+T%) y disminuya el virgen (-V%) para aumentar la fluidez del fundido.'
              : isDe
                  ? 'Recycling-Anteil (+T%) erhöhen und Jungmaterial (-V%) senken, um Schmelzfließfähigkeit zu steigern.'
                  : 'Increase recycled material percentage (+T%) and decrease virgin material percentage (-V%) to increase melt fluidity.',
        ),
      ];

  // —— Bobinador ——
  String get winderControls =>
      isEs ? 'Controles de bobinado' : isDe ? 'Wickelsteuerung' : 'Winding controls';
  String get startWinding =>
      isEs ? 'INICIAR BOBINADO' : isDe ? 'WICKELN STARTEN' : 'START WINDING';
  String get winderParameters =>
      isEs ? 'Parámetros' : isDe ? 'Parameter' : 'Parameters';
  String get winderDiameterChart =>
      isEs ? 'Gráfico de diámetro' : isDe ? 'Durchmesserdiagramm' : 'Diameter chart';
  String get pullRpm => isEs ? 'RPM tracción' : isDe ? 'Zug-RPM' : 'Pull rpm';
  String get metersTarget =>
      isEs ? 'Metros objetivo' : isDe ? 'Meter Soll' : 'Meters target';
  String get diamMinMm => isEs ? 'Diam min mm' : isDe ? 'Diam min mm' : 'Diam min mm';
  String get diamMaxMm => isEs ? 'Diam max mm' : isDe ? 'Diam max mm' : 'Diam max mm';
  String rolledUpMeters(String label) => isEs
      ? 'Enrollado: $label metros'
      : isDe
          ? 'Aufgewickelt: $label Meter'
          : 'Rolled up: $label meters';
  String get adjustDiameterOffset =>
      isEs ? 'Ajustar OFFSET de diámetro' : isDe ? 'Durchmesser-OFFSET anpassen' : 'Adjust diameter OFFSET';
  String get offsetToApply =>
      isEs ? 'OFFSET a aplicar (DOFF)' : isDe ? 'Anzuwendender OFFSET (DOFF)' : 'OFFSET to apply (DOFF)';
  String get winderOffsetConfirmHint => isEs
      ? 'Confirmar envía HALL SET DOFF al MK3 y guarda EEPROM (MS).'
      : isDe
          ? 'Bestätigen sendet HALL SET DOFF an den MK3 und speichert EEPROM (MS).'
          : 'Confirm sends HALL SET DOFF to the MK3 and saves EEPROM (MS).';
  String get applyingWinder => isEs ? 'Aplicando…' : isDe ? 'Wird angewendet…' : 'Applying…';
  String get diameterLimit =>
      isEs ? 'Límite de diámetro' : isDe ? 'Durchmesserlimit' : 'Diameter limit';
  String filamentTooThinOrThick(String mm) => isEs
      ? 'Filamento muy fino o grueso: $mm mm'
      : isDe
          ? 'Filament zu dünn oder zu dick: $mm mm'
          : 'Filament too thin or too thick: $mm mm';
  String get diameterLimitsMm =>
      isEs ? 'Límites de diámetro (mm)' : isDe ? 'Durchmesserlimits (mm)' : 'Diameter limits (mm)';
  String get winderContinueSending => isEs
      ? 'Reanudando tracción a 80 rpm...'
      : isDe
          ? 'Zug auf 80 rpm wird fortgesetzt...'
          : 'Resuming pull at 80 rpm...';
  String get winderStopSending => isEs
      ? 'Deteniendo bobinado...'
      : isDe
          ? 'Wickeln wird gestoppt...'
          : 'Stopping winder...';
  String get winderAdjustLimitsContinue => isEs
      ? 'Ajuste límites si hace falta y pulse Continuar para reanudar el bobinado.'
      : isDe
          ? 'Limits ggf. anpassen, dann Weiter zum Fortsetzen des Wickelns.'
          : 'Adjust limits if needed, then Continue to resume winding.';
  String get winderErrNeedDlcdDprom => isEs
      ? 'Se necesitan DLCD y diámetro promedio (Dprom) para calcular el offset.'
      : isDe
          ? 'DLCD und Mitteldurchmesser (Dprom) werden für Offset-Berechnung benötigt.'
          : 'Need DLCD and average diameter (Dprom) to calculate offset.';
  String get winderErrContinueIncomplete => isEs
      ? 'WINDER CONTINUE no completó (verifique gateway / bloqueo CSV).'
      : isDe
          ? 'WINDER CONTINUE nicht abgeschlossen (Gateway / CSV-Sperre prüfen).'
          : 'WINDER CONTINUE did not complete (check gateway / CSV lock).';

  // —— Análisis ——
  String get analysisMaterialLog =>
      isEs ? 'Registro de material (csv_logs Pi)' : isDe ? 'Materialprotokoll (Pi csv_logs)' : 'Material log (Pi csv_logs)';
  String get analysisMaterialLogHint => isEs
      ? 'Seleccione un material (último csv) o un historial fechado debajo. Hasta ${AppConfig.csvHistoryMaxPerMaterial} por código (anillo FIFO).'
      : isDe
          ? 'Material (letzte CSV) oder datierten Verlauf darunter wählen. Bis ${AppConfig.csvHistoryMaxPerMaterial} pro Code (FIFO-Ring).'
          : 'Select a material (latest csv) or a dated history under it. Up to ${AppConfig.csvHistoryMaxPerMaterial} per code (FIFO ring).';
  String get analysisDeleteHistoryTitle =>
      isEs ? 'Borrar historial' : isDe ? 'Verlauf löschen' : 'Delete history';
  String analysisDeleteHistoryMessage(String label) => isEs
      ? '¿Borrar esta entrada?\n$label'
      : isDe
          ? 'Diesen Eintrag löschen?\n$label'
          : 'Delete this entry?\n$label';
  String get analysisDeleteHistoryButton =>
      isEs ? 'BORRAR ENTRADA' : isDe ? 'EINTRAG LÖSCHEN' : 'DELETE ENTRY';
  String get analysisClearHistoryTitle =>
      isEs ? 'Vaciar historial' : isDe ? 'Verlauf leeren' : 'Clear history';
  /// CSV en la Pi cuyo material ya no está en el catálogo.
  String get analysisOrphanLabel =>
      isEs ? 'sin material' : isDe ? 'ohne Material' : 'no material';
  String analysisClearHistoryMessage(String materialId, int count) => isEs
      ? '¿Vaciar los $count historiales de $materialId?\n(No borra el CSV actual $materialId.csv)'
      : isDe
          ? '$count Verläufe von $materialId leeren?\n(Aktuelle CSV $materialId.csv bleibt)'
          : 'Clear $count history entries for $materialId?\n(Does not delete current $materialId.csv)';
  String get analysisClearHistoryButton =>
      isEs ? 'VACIAR HISTORIAL' : isDe ? 'VERLAUF LEEREN' : 'CLEAR HISTORY';
  String get analysisLiveCapture =>
      isEs ? 'Captura en vivo' : isDe ? 'Live-Aufnahme' : 'Live capture';
  String get analysisFileLogSource =>
      isEs ? 'Archivo guardado' : isDe ? 'Gespeicherte Datei' : 'Saved file';
  String get analysisLiveCaptureHint => isEs
      ? 'Misma telemetría del poll automático (Extruder/Winder). Puede analizar en paralelo mientras la máquina funciona.'
      : isDe
          ? 'Gleiche Telemetrie wie beim automatischen Poll (Extruder/Winder). Parallel analysieren während der Maschine läuft.'
          : 'Same telemetry as the automatic poll (Extruder/Winder). Analyze in parallel while the machine runs.';
  String analysisRecordingLabel(String materialId, int rows) => isEs
      ? 'Grabando staging G (seleccionado $materialId) · $rows registros'
      : isDe
          ? 'Staging G (gewählt $materialId) · $rows Datensätze'
          : 'Recording staging G (selected $materialId) · $rows records';
  String csvPersistTitle(String materialId) => isEs
      ? '¿Persistir material $materialId?'
      : isDe
          ? 'Material $materialId speichern?'
          : 'Persist raw material $materialId?';
  String get csvPersistNoteLabel => isEs
      ? 'Nombre del lote (opcional)'
      : isDe
          ? 'Chargenname (optional)'
          : 'Batch name (optional)';
  String get csvPersistNoteHint => isEs
      ? 'Máx. ${CsvFileEntry.maxNoteLength} caracteres; se ve en Análisis'
      : isDe
          ? 'Max. ${CsvFileEntry.maxNoteLength} Zeichen; sichtbar in Analyse'
          : 'Max ${CsvFileEntry.maxNoteLength} chars; shown in Analysis';
  String get csvPersistYes =>
      isEs ? 'Persistir' : isDe ? 'Speichern' : 'Persist';
  String get csvPersistNo =>
      isEs ? 'No' : isDe ? 'Nein' : 'No';
  String csvPersistDone(String materialId) => isEs
      ? 'Corrida guardada en material $materialId.'
      : isDe
          ? 'Lauf in Material $materialId gespeichert.'
          : 'Run saved to material $materialId.';
  String csvPersistDoneWithHistory(String materialId, String historyId) => isEs
      ? 'Guardado en $materialId y historial $historyId.'
      : isDe
          ? 'Gespeichert in $materialId und Verlauf $historyId.'
          : 'Saved to $materialId and history $historyId.';
  String get analysisLiveRecording => isEs
      ? 'Grabación en curso'
      : isDe
          ? 'Laufende Aufnahme'
          : 'Live recording';
  String analysisLiveSourceLabel(int rows) => isEs
      ? 'Captura en vivo · $rows registros'
      : isDe
          ? 'Live-Aufnahme · $rows Datensätze'
          : 'Live capture · $rows records';
  String get analysisClearLive =>
      isEs ? 'LIMPIAR VIVO' : isDe ? 'LIVE LEEREN' : 'CLEAR LIVE';
  String get refreshList =>
      isEs ? 'ACTUALIZAR LISTA' : isDe ? 'LISTE AKTUALISIEREN' : 'REFRESH LIST';
  String get analysisViewNav =>
      isEs ? 'Navegación VIEW y registro' : isDe ? 'VIEW- und Datensatznavigation' : 'VIEW and record navigation';
  String analysisRegWindow(int reg, int total, int window, int pct) => isEs
      ? 'Reg $reg / $total · ventana $window (VIEW $pct %)'
      : isDe
          ? 'Reg $reg / $total · Fenster $window (VIEW $pct %)'
          : 'Reg $reg / $total · window $window (VIEW $pct %)';
  String analysisCsvRecordsAround(int selected) => isEs
      ? 'Registros CSV (±5 alrededor de reg $selected)'
      : isDe
          ? 'CSV-Datensätze (±5 um Reg $selected)'
          : 'CSV records (±5 around reg $selected)';
  String get fineFilament =>
      isEs ? 'Filamento fino' : isDe ? 'Dünnes Filament' : 'Fine filament';
  String get thickFilament =>
      isEs ? 'Filamento grueso' : isDe ? 'Dickes Filament' : 'Thick filament';
  String get enableFilter =>
      isEs ? 'Activar filtro' : isDe ? 'Filter aktivieren' : 'Enable filter';
  String analysisFilterTooThin(int reg) => isEs
      ? 'Filamento muy fino (reg $reg)'
      : isDe
          ? 'Filament zu dünn (Reg $reg)'
          : 'Filament too thin (reg $reg)';
  String analysisFilterTooThick(int reg) => isEs
      ? 'Filamento muy grueso (reg $reg)'
      : isDe
          ? 'Filament zu dick (Reg $reg)'
          : 'Filament too thick (reg $reg)';
  String get analysisNoOutOfRange => isEs
      ? 'No se encontraron registros fuera de rango'
      : isDe
          ? 'Keine außerhalb des Bereichs liegenden Datensätze'
          : 'No out-of-range records found';
  String analysisErrNoRows(String id) => isEs
      ? 'Sin filas en csv_logs/$id.csv (grabar primero o verificar id de material).'
      : isDe
          ? 'Keine Zeilen in csv_logs/$id.csv (zuerst aufzeichnen oder Material-ID prüfen).'
          : 'No rows in csv_logs/$id.csv (record first or check material id).';
  String get chartNeedSamples => isEs
      ? 'Recopile al menos 2 muestras para el gráfico.'
      : isDe
          ? 'Mindestens 2 Proben für das Diagramm sammeln.'
          : 'Collect at least 2 samples for the chart.';
  String get chartNoNumericDiameter => isEs
      ? 'Sin valores numéricos de diámetro/longitud en el buffer.'
      : isDe
          ? 'Keine numerischen Durchmesser-/Längenwerte im Puffer.'
          : 'No numeric diameter/length values in buffer.';
  String get noRowsHistogramWindow => isEs
      ? 'Sin filas en la ventana actual del histograma.'
      : isDe
          ? 'Keine Zeilen im aktuellen Histogrammfenster.'
          : 'No rows in the current histogram window.';

  // —— Consola ——
  String get consoleCommandInput =>
      isEs ? 'Entrada de comandos' : isDe ? 'Befehlseingabe' : 'Command input';
  String get consoleQuickChips =>
      isEs ? 'Accesos rápidos' : isDe ? 'Schnellzugriff' : 'Quick chips';
  String get consoleCopyLog =>
      isEs ? 'Copiar log' : isDe ? 'Log kopieren' : 'Copy log';
  String get consoleLogCopied => isEs
      ? 'Log copiado al portapapeles.'
      : isDe
          ? 'Log in die Zwischenablage kopiert.'
          : 'Log copied to clipboard.';
  String get consoleLogDownloaded => isEs
      ? 'HTTP LAN: portapapeles bloqueado; log descargado como .txt.'
      : isDe
          ? 'HTTP-LAN: Zwischenablage blockiert; Log als .txt heruntergeladen.'
          : 'HTTP LAN: clipboard blocked; log downloaded as .txt.';
  String get consoleLogCopyFailed => isEs
      ? 'No se pudo copiar el log.'
      : isDe
          ? 'Log konnte nicht kopiert werden.'
          : 'Could not copy the log.';
  String get consoleLogEmpty => isEs
      ? 'No hay líneas para copiar.'
      : isDe
          ? 'Keine Zeilen zum Kopieren.'
          : 'Nothing to copy.';
  String get consoleLineCopied => isEs
      ? 'Línea copiada.'
      : isDe
          ? 'Zeile kopiert.'
          : 'Line copied.';
  String get showAuto => isEs ? 'Mostrar auto' : isDe ? 'Auto anzeigen' : 'Show auto';
  String get hideAuto => isEs ? 'Ocultar auto' : isDe ? 'Auto ausblenden' : 'Hide auto';
  String get consoleSend => isEs ? 'Enviar' : isDe ? 'Senden' : 'Send';
  String get consoleReady => isEs
      ? 'Consola lista. Escriba un comando (ej. HELP, WHOAREYOU).'
      : isDe
          ? 'Konsole bereit. Befehl eingeben (z. B. HELP, WHOAREYOU).'
          : 'Console ready. Type a command (e.g. HELP, WHOAREYOU).';
  String get consoleReadyAdmin => isEs
      ? 'Consola lista (admin: texto libre; SO y PI bloqueados).'
      : isDe
          ? 'Konsole bereit (Admin: Freitext; SO und PI blockiert).'
          : 'Console ready (admin: free text; SO and PI blocked).';
  String get consoleReadyOperator => isEs
      ? 'Consola lista (operador: solo botones CONECTAR, WIFI, …).'
      : isDe
          ? 'Konsole bereit (Operator: nur Chips CONECTAR, WIFI, …).'
          : 'Console ready (operator: chips only — CONECTAR, WIFI, …).';
  String get consoleAutoShown => isEs
      ? 'Los comandos de poll automático se mostrarán en la consola.'
      : isDe
          ? 'Automatische Poll-Befehle werden in der Konsole angezeigt.'
          : 'Automatic poll commands will be shown in the console.';
  String get consoleAutoHidden => isEs
      ? 'Los comandos de poll automático están ocultos (los manuales siguen visibles).'
      : isDe
          ? 'Automatische Poll-Befehle sind ausgeblendet (manuelle Befehle weiter sichtbar).'
          : 'Automatic poll commands are hidden (manual commands still appear).';
  String get unpairGateway =>
      isEs ? 'Desemparejar gateway' : isDe ? 'Gateway entkoppeln' : 'Unpair gateway';
  String get changeToken =>
      isEs ? 'Cambiar token' : isDe ? 'Token wechseln' : 'Change token';
  String get connectionOnline => 'ONLINE';
  String get connectionOffline => isEs ? 'FUERA DE LÍNEA' : isDe ? 'OFFLINE' : 'OFFLINE';
  String get connectionNoGateway =>
      isEs ? 'SIN GATEWAY' : isDe ? 'KEIN GATEWAY' : 'NO GATEWAY';

  String authErrorMessage(String code) {
    if (isEs) {
      return switch (code) {
        'empty-credentials' => 'Ingrese correo y contraseña.',
        'empty-email' => 'Ingrese su correo electrónico.',
        'invalid-email' => 'Correo electrónico no válido.',
        'user-disabled' => 'Cuenta deshabilitada.',
        'user-not-found' => 'Cuenta no encontrada. Use "Primera vez — crear cuenta".',
        'wrong-password' => 'Contraseña incorrecta.',
        'email-already-in-use' => 'Correo ya registrado. Use "Iniciar sesión".',
        'weak-password' => 'Contraseña demasiado débil (mínimo 6 caracteres).',
        'invalid credentials' => 'Usuario o contraseña incorrectos.',
        'invalid-credential' =>
          'Correo o contraseña incorrectos, o la cuenta no existe. Si es su primera vez, pulse "Primera vez — crear cuenta".',
        'operation-not-allowed' =>
          'El inicio de sesión por correo/contraseña NO está habilitado en Firebase.',
        'unauthorized-domain' => 'Dominio no autorizado.',
        'network-request-failed' => 'No se puede conectar a Firebase. Verifique internet o firewall.',
        'too-many-requests' => 'Demasiados intentos. Espere un minuto e intente de nuevo.',
        'api-key-not-valid' || 'api-key-not-valid.-please-pass-a-valid-api-key.' =>
          'Clave API inválida o bloqueada.',
        _ => code,
      };
    }
    if (isDe) {
      return switch (code) {
        'empty-credentials' => 'Bitte E-Mail und Passwort eingeben.',
        'empty-email' => 'Bitte Ihre E-Mail-Adresse eingeben.',
        'invalid-email' => 'Ungültige E-Mail-Adresse.',
        'user-disabled' => 'Konto deaktiviert.',
        'user-not-found' => 'Konto nicht gefunden. Verwenden Sie „Zum ersten Mal — Konto erstellen“.',
        'wrong-password' => 'Falsches Passwort.',
        'email-already-in-use' => 'E-Mail wird bereits verwendet. Nutzen Sie „Anmelden“.',
        'weak-password' => 'Passwort zu schwach (mindestens 6 Zeichen).',
        'invalid credentials' => 'Falscher Benutzer oder falsches Passwort.',
        'invalid-credential' =>
          'Falsche E-Mail oder falsches Passwort, oder das Konto existiert nicht. Wenn Sie zum ersten Mal hier sind, tippen Sie auf „Zum ersten Mal — Konto erstellen“.',
        'operation-not-allowed' => 'Die Anmeldung per E-Mail/Passwort ist in Firebase NICHT aktiviert.',
        'unauthorized-domain' => 'Nicht autorisierte Domain.',
        'network-request-failed' => 'Keine Verbindung zu Firebase. Bitte Internet oder Firewall prüfen.',
        'too-many-requests' => 'Zu viele Versuche. Bitte warten Sie eine Minute und versuchen Sie es erneut.',
        'api-key-not-valid' || 'api-key-not-valid.-please-pass-a-valid-api-key.' =>
          'API-Schlüssel ungültig oder blockiert.',
        _ => code,
      };
    }
    return switch (code) {
      'empty-credentials' => 'Enter email and password.',
      'empty-email' => 'Enter your email address.',
      'invalid-email' => 'Invalid email address.',
      'user-disabled' => 'Account disabled.',
      'user-not-found' => 'Account not found. Use "First time — create account".',
      'wrong-password' => 'Wrong password.',
      'email-already-in-use' => 'Email already in use. Use "Sign in".',
      'weak-password' => 'Weak password (minimum 6 characters).',
      'invalid credentials' => 'Wrong username or password.',
      'invalid-credential' =>
        'Wrong email or password, or the account does not exist. If this is your first time, tap "First time — create account".',
      'operation-not-allowed' => 'Email/password sign-in is NOT enabled in Firebase.',
      'unauthorized-domain' => 'Unauthorized domain.',
      'network-request-failed' => 'Cannot connect to Firebase. Check internet or firewall.',
      'too-many-requests' => 'Too many attempts. Wait a minute and try again.',
      'api-key-not-valid' || 'api-key-not-valid.-please-pass-a-valid-api-key.' =>
        'Invalid or blocked API key.',
      _ => code,
    };
  }
}

class L10nStep {
  const L10nStep({required this.title, required this.body});
  final String title;
  final String body;
}
