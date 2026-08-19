/*
  FR3D USB CSV telemetry (instantaneous snapshot every 10 s, Model A boot).
*/

#include "Configuration.h"

#ifdef FR3D_CSV_TELEMETRY

#if !defined(ULTRA_LCD)
void fr3d_csv_telemetry_poll(void) {}
void fr3d_csv_sync_sample_timer(void) {}
void fr3d_csv_request_usb_row(void) {}
void fr3d_diam_poll_samples(void) {}
void fr3d_pred_ui_print_token(void) {}
void fr3d_pred_on_extrude_stop(void) {}
uint16_t fr3d_diam_fifo_avg_x1000 = 0;
uint8_t fr3d_diam_src = 0;
uint8_t fr3d_diam_host_fresh(void) { return 0; }
void fr3d_diam_host_set(float mm) { (void)mm; }
float fr3d_diam_host_get(void) { return 1.75f; }
void fr3d_diam_src_set(uint8_t src) { fr3d_diam_src = (src > 2) ? 0 : src; }
#else

uint16_t fr3d_diam_fifo_avg_x1000 = 0;
uint8_t fr3d_diam_src = 0; /* 0=A3 1=USB 2=MANUAL */

#include "MK3.h"
#include "temperature.h"
#include "ultralcd.h"
#include <Arduino.h>
#include <stdio.h>

#define FR3D_HOST_DIAM_STALE_MS 5000UL
static float fr3d_host_diam_mm = 1.75f;
static unsigned long fr3d_host_diam_ms = 0;

static void fr3d_diam_window_reset(float seed_value, unsigned long now);
static uint8_t fr3d_diam_for_pred(float *d_mean, float *d_span);

uint8_t fr3d_diam_host_fresh(void)
{
  if (fr3d_diam_src == 2) return 1; /* Manual: Ø local, no caduca */
  if (fr3d_diam_src != 1) return 0;
  if (fr3d_host_diam_ms == 0UL) return 0;
  return ((unsigned long)(millis() - fr3d_host_diam_ms) <= FR3D_HOST_DIAM_STALE_MS) ? 1 : 0;
}

float fr3d_diam_host_get(void)
{
  return fr3d_host_diam_mm;
}

void fr3d_diam_host_set(float mm)
{
  if (mm < 1.20f) mm = 1.20f;
  if (mm > 2.80f) mm = 2.80f;
  const float prev = fr3d_host_diam_mm;
  fr3d_host_diam_mm = mm;
  fr3d_host_diam_ms = millis();
  /* Manual: el Ø es el calibre del operador. Vaciar FIFO Hall/USB viejo. */
  if (fr3d_diam_src == 2) {
    float d = mm - prev;
    if (d < 0.0f) d = -d;
    if (d >= 0.0005f)
      fr3d_diam_window_reset(mm, millis());
  }
}

void fr3d_diam_src_set(uint8_t src)
{
  if (src > 2) src = 0;
  const uint8_t prev = fr3d_diam_src;
  fr3d_diam_src = src;
  if (fr3d_diam_src == 0)
    fr3d_host_diam_ms = 0UL;
  else if (fr3d_diam_src == 2 && fr3d_host_diam_ms == 0UL)
    fr3d_host_diam_ms = millis();
  if (prev != fr3d_diam_src) {
    const float seed = (fr3d_diam_src == 0) ? 1.75f : fr3d_host_diam_mm;
    fr3d_diam_window_reset(seed, millis());
  }
}

#define FR3D_DIAM_SAMPLE_MS 500UL
#define FR3D_DIAM_FIFO_CAPACITY 20U

static unsigned long fr3d_csv_period_ms(void)
{
  /* Periodo de fusión fijo (FR3D_CSV_CYCLE_S_DEFAULT = 2 s). */
  uint8_t sec = fr3d_csv_cycle_s;
  if (sec < (uint8_t)FR3D_CSV_CYCLE_S_MIN) sec = (uint8_t)FR3D_CSV_CYCLE_S_MIN;
  if (sec > (uint8_t)FR3D_CSV_CYCLE_S_MAX) sec = (uint8_t)FR3D_CSV_CYCLE_S_MAX;
  return (unsigned long)sec * 1000UL;
}

uint16_t fr3d_pred_median_10s_x1000 = 0;
char fr3d_pred_ui_mode_char = ' ';
char fr3d_pred_ui_adjust_char_0 = ' ';
char fr3d_pred_ui_adjust_char_1 = ' ';
char fr3d_pred_ui_sign_char = ' ';
char fr3d_pred_ui_last_axis_char = '-';
char fr3d_pred_ui_last_sign_char = '-';
uint8_t fr3d_pred_ui_last_value_valid = 0;
float fr3d_pred_ui_last_value = 0.0f;

static bool fr3d_csv_inited = false;
static uint32_t fr3d_csv_seq = 0;
static unsigned long fr3d_csv_next_ms = 0;
static uint8_t fr3d_csv_header_sent = 0;
static uint8_t fr3d_csv_usb_emit_pending = 0;
static unsigned long fr3d_diam_next_sample_ms = 0;
static float fr3d_diam_prom_10s = 0.0f;
static float fr3d_diam_median_10s = 0.0f;
static float fr3d_diam_min_10s = 0.0f;
static float fr3d_diam_max_10s = 0.0f;
static float fr3d_diam_fifo[FR3D_DIAM_FIFO_CAPACITY];
static uint8_t fr3d_diam_fifo_head = 0; // Next write index.
static uint8_t fr3d_diam_samples_n = 0; // Valid samples in FIFO [0..20].
// Hall clamps "no filament" near 1.50 mm; reject isolated dips into that band after stable filament.
static float fr3d_diam_prev_raw_mm = 0.0f;
static float fr3d_diam_last_accepted_mm = 0.0f;
static uint8_t fr3d_diam_median_pub_inited = 0;
static float fr3d_diam_median_pending_mm = 0.0f;
static uint8_t fr3d_diam_median_pending_n = 0;
// CSV ligero para auditar si el corrector de diametro actuo entre filas de CSV (10 s).
static uint16_t fr3d_diam_drop_floor_total = 0;
static uint16_t fr3d_diam_drop_floor_last_csv = 0;
static uint8_t fr3d_diam_jump_hold_since_csv = 0;
static uint16_t fr3d_diam_raw_samples_total = 0;
static uint16_t fr3d_diam_raw_samples_last_csv = 0;
static uint16_t fr3d_diam_accepted_samples_total = 0;
static uint16_t fr3d_diam_accepted_samples_last_csv = 0;
static float fr3d_diam_med_raw_last_10s = 0.0f;
static uint32_t fr3d_pred_fusion_id = 0;
static int32_t fr3d_pred_last_t_change_fusion = -1000000000L;
static uint8_t fr3d_pred_transport_hold_active = 0;
static float fr3d_pred_transport_l_ref_mm = 0.0f;
static unsigned long fr3d_pred_transport_hold_start_ms = 0;
static uint8_t fr3d_pred_ui_track_inited = 0;
static float fr3d_pred_ui_prev_r = 0.0f;
static int fr3d_pred_ui_prev_t = 0;
static char fr3d_pred_msg_main[120] = "-";
static char fr3d_pred_msg_detail[180] = "-";
/* Respetar márgenes hasta quedar encajonado (E y T en bandas margen fuera de banda D); luego usar margen efectivo 0 hasta volver dentro de banda. */
#ifndef FR3D_PRED_MARGIN_BYPASS_STREAK
#define FR3D_PRED_MARGIN_BYPASS_STREAK 2
#endif
static uint8_t fr3d_pred_margin_bypass = 0;
static uint8_t fr3d_pred_margin_corner_streak = 0;

static uint8_t fr3d_pred_ep_inited = 0;
static float fr3d_pred_ep_e0 = 0.0f;
static float fr3d_pred_ep_p0 = 0.0f;
static uint8_t fr3d_pred_ep_dead = 0;
static uint8_t fr3d_pred_ep_e_up = 0;
static unsigned long fr3d_pred_ep_dead_since_ms = 0;
static unsigned long fr3d_pred_opt_freeze_until_ms = 0;
static uint8_t fr3d_pred_p_ref_inited = 0;
static float fr3d_pred_p_ref = 0.0f;
static uint8_t fr3d_pred_opt_diam_out_streak = 0;
static uint8_t fr3d_pred_opt_acted_last = 0;
static unsigned long fr3d_pred_in_band_since_ms = 0;

static void fr3d_pred_ep_reset(float e, float p)
{
  fr3d_pred_ep_e0 = e;
  fr3d_pred_ep_p0 = p;
  fr3d_pred_ep_inited = 1;
  fr3d_pred_ep_dead = 0;
  fr3d_pred_ep_e_up = 0;
  fr3d_pred_ep_dead_since_ms = 0;
}

void fr3d_pred_on_extrude_stop(void)
{
  fr3d_pred_optimize = 0;
  fr3d_pred_ep_inited = 0;
  fr3d_pred_ep_dead = 0;
  fr3d_pred_ep_e_up = 0;
  fr3d_pred_ep_dead_since_ms = 0;
  fr3d_pred_opt_freeze_until_ms = 0;
  fr3d_pred_p_ref_inited = 0;
  fr3d_pred_opt_diam_out_streak = 0;
  fr3d_pred_opt_acted_last = 0;
  fr3d_pred_in_band_since_ms = 0;
  fr3d_pred_transport_hold_active = 0;
}

static void fr3d_pred_apply_e(float next_e)
{
  extruder_rpm_set = constrain(next_e, EXTRUDER_RPM_MIN, EXTRUDER_RPM_MAX);
}

static float fr3d_pred_pull_rpm(void)
{
  float pc = pcirc;
  if (pc < 1.0f) pc = DEFAULT_PULLER_WHEEL_CIRC;
  return puller_feedrate * (60.0f / pc);
}

static void fr3d_pred_begin_freeze(void)
{
  fr3d_pred_opt_freeze_until_ms = millis() + FR3D_PRED_OPT_FREEZE_MS;
  fr3d_pred_opt_acted_last = 0;
  fr3d_pred_opt_diam_out_streak = 0;
}

static uint8_t fr3d_pred_freeze_active(void)
{
  if (fr3d_pred_opt_freeze_until_ms == 0) return 0;
  if (millis() >= fr3d_pred_opt_freeze_until_ms) {
    fr3d_pred_opt_freeze_until_ms = 0;
    return 0;
  }
  return 1;
}

static void fr3d_pred_set_fan_pct(int pct)
{
  if (pct < FR3D_PRED_F_MIN_PCT) pct = FR3D_PRED_F_MIN_PCT;
  if (pct > FR3D_PRED_F_MAX_PCT) pct = FR3D_PRED_F_MAX_PCT;
  default_winder_speed = pct;
  if (winder_rpm_factor > 0)
    winderSpeed = default_winder_speed * 255 / winder_rpm_factor;
}

static void fr3d_pred_mark_transport_hold(void)
{
  fr3d_pred_transport_hold_active = 1;
  fr3d_pred_transport_l_ref_mm = extrude_length;
  fr3d_pred_transport_hold_start_ms = millis();
}

/* Libera el hold si ya pasó ΔL o el timeout. 1 = seguir esperando. */
static uint8_t fr3d_pred_transport_hold_tick(char *detail, size_t detail_sz)
{
  if (!fr3d_pred_transport_hold_active) return 0;
  const float hold_m = max(0.0f, fr3d_pred_hold_m);
  const uint16_t hold_to_s = fr3d_pred_hold_timeout_s;
  const unsigned long now_ms = millis();
  const unsigned long elapsed_ms = now_ms - fr3d_pred_transport_hold_start_ms;
  const bool timed_out = (hold_to_s > 0) && (elapsed_ms >= (unsigned long)hold_to_s * 1000UL);
  float delta_m = 0.0f;
  bool length_reset = false;
  if (extrude_length + 0.5f < fr3d_pred_transport_l_ref_mm) {
    length_reset = true;
  } else {
    delta_m = (extrude_length - fr3d_pred_transport_l_ref_mm) / 1000.0f;
  }
  const bool meters_ok = (hold_m <= 0.0001f) || (delta_m + 0.0001f >= hold_m);
  if (length_reset || timed_out || meters_ok) {
    fr3d_pred_transport_hold_active = 0;
    return 0;
  }
  if (detail != NULL && detail_sz > 0) {
    snprintf(
        detail,
        detail_sz,
        "Hold transporte: ΔL=%.3f/%.3f m t=%lu/%u s",
        delta_m,
        hold_m,
        (unsigned long)(elapsed_ms / 1000UL),
        (unsigned int)hold_to_s);
  }
  return 1;
}

static float fr3d_absf(float v) { return (v < 0.0f) ? -v : v; }

static void fr3d_pred_set_main(const char *msg)
{
  if (!msg || !*msg) msg = "-";
  snprintf(fr3d_pred_msg_main, sizeof(fr3d_pred_msg_main), "%s", msg);
}

static void fr3d_pred_set_detail(const char *msg)
{
  if (!msg || !*msg) msg = "-";
  snprintf(fr3d_pred_msg_detail, sizeof(fr3d_pred_msg_detail), "%s", msg);
}

static void fr3d_pred_set_pair(const char *main_msg, const char *detail_msg)
{
  fr3d_pred_set_main(main_msg);
  fr3d_pred_set_detail(detail_msg);
}

static void fr3d_pred_ui_clear(void)
{
  fr3d_pred_ui_mode_char = ' ';
  fr3d_pred_ui_adjust_char_0 = ' ';
  fr3d_pred_ui_adjust_char_1 = ' ';
  fr3d_pred_ui_sign_char = ' ';
}

/* Estados LCD/Flutter: SIN A | A | AH | AB | AE± | AT± */
static void fr3d_pred_ui_set_idle(char reason_c)
{
  if (fr3d_pred_enabled == 0 || fr3d_pred_mode == 0) {
    fr3d_pred_ui_mode_char = '-';
    fr3d_pred_ui_adjust_char_0 = ' ';
    fr3d_pred_ui_adjust_char_1 = ' ';
    fr3d_pred_ui_sign_char = ' ';
    return;
  }
  fr3d_pred_ui_mode_char = 'A';
  fr3d_pred_ui_adjust_char_0 = reason_c; /* H hold, B banda, S settle, C cal, O DH off, G gate, N no diam, P slip, U under-melt, Z freeze */
  fr3d_pred_ui_adjust_char_1 = ' ';
  fr3d_pred_ui_sign_char = ' ';
}

static void fr3d_pred_ui_set(char mode_c, bool changed_r, bool changed_t, float dr, int dt, float next_r, int next_t)
{
  if (fr3d_pred_enabled == 0 || fr3d_pred_mode == 0) {
    fr3d_pred_ui_set_idle(' ');
    return;
  }
  fr3d_pred_ui_mode_char = mode_c;
  // E = corrección sobre RPM del sinfín (extruder_rpm_set); R era tirador en un diseño anterior.
  fr3d_pred_ui_adjust_char_0 = changed_r ? 'E' : (changed_t ? 'T' : ' ');
  fr3d_pred_ui_adjust_char_1 = (changed_r && changed_t) ? 'T' : ' ';
  if (!changed_r && !changed_t) {
    fr3d_pred_ui_sign_char = ' ';
    return;
  }
  bool up = false;
  bool down = false;
  if (changed_r) {
    if (dr > 0.0f) up = true;
    if (dr < 0.0f) down = true;
  }
  if (changed_t) {
    if (dt > 0) up = true;
    if (dt < 0) down = true;
  }
  fr3d_pred_ui_sign_char = (up && !down) ? '+' : ((!up && down) ? '-' : ' ');

  // Persist the last applied/suggested adjustment for LCD line 2 until the next change.
  if (changed_t) {
    fr3d_pred_ui_last_axis_char = 'T';
    fr3d_pred_ui_last_sign_char = (dt > 0) ? '+' : ((dt < 0) ? '-' : '-');
    fr3d_pred_ui_last_value = (float)next_t;
    fr3d_pred_ui_last_value_valid = 1;
  } else if (changed_r) {
    fr3d_pred_ui_last_axis_char = 'E';
    fr3d_pred_ui_last_sign_char = (dr > 0.0f) ? '+' : ((dr < 0.0f) ? '-' : '-');
    fr3d_pred_ui_last_value = next_r;
    fr3d_pred_ui_last_value_valid = 1;
  }
}

void fr3d_pred_ui_print_token(void)
{
  /* echo:PREDUI,<token>,  — SIN A|A|AH|AB|AS|AC|AO|AG|AN|AP|AU|AZ|AE±|AT± */
  SERIAL_ECHO_START;
  SERIAL_ECHOPGM("PREDUI,");
  if (fr3d_pred_enabled == 0 || fr3d_pred_mode == 0) {
    SERIAL_ECHOPGM("SIN A");
  } else {
    const char a0 = fr3d_pred_ui_adjust_char_0;
    const char sg = fr3d_pred_ui_sign_char;
    SERIAL_ECHO('A');
    if (a0 == 'H' || a0 == 'B' || a0 == 'S' || a0 == 'C' || a0 == 'G' || a0 == 'N' || a0 == 'O' ||
        a0 == 'P' || a0 == 'U' || a0 == 'Z') {
      SERIAL_ECHO(a0);
    } else if ((a0 == 'E' || a0 == 'T') && (sg == '+' || sg == '-')) {
      SERIAL_ECHO(a0);
      SERIAL_ECHO(sg);
    }
  }
  SERIAL_ECHOLNPGM(",");
}

static uint16_t fr3d_quantize_mm_x1000(float mm)
{
  long v = (long)(mm * 1000.0f + 0.5f);
  if (v < 0L) v = 0L;
  if (v > 9999L) v = 9999L;
  return (uint16_t)v;
}

static void fr3d_diam_median_debounce_reset(float seed_mm)
{
  fr3d_diam_median_10s = seed_mm;
  fr3d_pred_median_10s_x1000 = fr3d_quantize_mm_x1000(seed_mm);
  fr3d_diam_median_pub_inited = 1;
  fr3d_diam_median_pending_mm = seed_mm;
  fr3d_diam_median_pending_n = 0;
}

/** Publica la mediana de la ventana (raw) con retardo ante saltos bruscos vs el valor ya publicado. */
static void fr3d_diam_apply_median_jump_debounce(float raw_med_mm)
{
  if (!fr3d_diam_median_pub_inited)
  {
    fr3d_diam_median_debounce_reset(raw_med_mm);
    return;
  }

  if (fr3d_diam_jump_debounce_mm <= 0.0f)
  {
    fr3d_diam_median_10s = raw_med_mm;
    fr3d_pred_median_10s_x1000 = fr3d_quantize_mm_x1000(raw_med_mm);
    fr3d_diam_median_pending_n = 0;
    return;
  }

  const float match_tol = (fr3d_diam_pending_match_mm > 0.0f) ? fr3d_diam_pending_match_mm : 0.001f;
  const float d = fr3d_absf(raw_med_mm - fr3d_diam_median_10s);
  if (d <= fr3d_diam_jump_debounce_mm)
  {
    fr3d_diam_median_10s = raw_med_mm;
    fr3d_pred_median_10s_x1000 = fr3d_quantize_mm_x1000(raw_med_mm);
    fr3d_diam_median_pending_n = 0;
    return;
  }

  /* Published stuck at Hall floor (~1.50 mm) while window median shows real filament:
     require one confirm window (not two) so recovery toward ~1.75 is not blocked. */
  if (fr3d_diam_median_10s <= 1.52f && raw_med_mm >= 1.53f && d > fr3d_diam_jump_debounce_mm)
  {
    const float up_tol = match_tol * 2.5f;
    if (fr3d_diam_median_pending_n == 0)
    {
      fr3d_diam_median_pending_mm = raw_med_mm;
      fr3d_diam_median_pending_n = 1;
      fr3d_diam_jump_hold_since_csv = 1;
      return;
    }
    if (fr3d_absf(raw_med_mm - fr3d_diam_median_pending_mm) <= up_tol)
    {
      fr3d_diam_median_10s = raw_med_mm;
      fr3d_pred_median_10s_x1000 = fr3d_quantize_mm_x1000(raw_med_mm);
      fr3d_diam_median_pending_n = 0;
      return;
    }
    fr3d_diam_median_pending_mm = raw_med_mm;
    fr3d_diam_median_pending_n = 1;
    fr3d_diam_jump_hold_since_csv = 1;
    return;
  }

  if (fr3d_diam_median_pending_n == 0)
  {
    fr3d_diam_median_pending_mm = raw_med_mm;
    fr3d_diam_median_pending_n = 1;
    fr3d_diam_jump_hold_since_csv = 1;
    return;
  }

  if (fr3d_absf(raw_med_mm - fr3d_diam_median_pending_mm) <= match_tol)
  {
    fr3d_diam_median_pending_n++;
    if (fr3d_diam_median_pending_n >= 2)
    {
      fr3d_diam_median_10s = raw_med_mm;
      fr3d_pred_median_10s_x1000 = fr3d_quantize_mm_x1000(raw_med_mm);
      fr3d_diam_median_pending_n = 0;
    }
  }
  else
  {
    fr3d_diam_median_pending_mm = raw_med_mm;
    fr3d_diam_median_pending_n = 1;
    fr3d_diam_jump_hold_since_csv = 1;
  }
}

static void fr3d_update_median_10s(void)
{
  float raw_med;
  if (fr3d_diam_samples_n == 0)
    raw_med = fr3d_diam_prom_10s;
  else
  {
    float v[FR3D_DIAM_FIFO_CAPACITY];
    const uint8_t n = fr3d_diam_samples_n;
    for (uint8_t i = 0; i < n; ++i) v[i] = fr3d_diam_fifo[i];
    for (uint8_t i = 1; i < n; ++i)
    {
      float key = v[i];
      int8_t j = (int8_t)i - 1;
      while (j >= 0 && v[(uint8_t)j] > key)
      {
        v[(uint8_t)(j + 1)] = v[(uint8_t)j];
        --j;
      }
      v[(uint8_t)(j + 1)] = key;
    }
    if ((n & 1U) != 0U)
      raw_med = v[n / 2U];
    else
      raw_med = 0.5f * (v[n / 2U - 1U] + v[n / 2U]);
  }
  fr3d_diam_med_raw_last_10s = raw_med;
  fr3d_diam_apply_median_jump_debounce(raw_med);
}

static void fr3d_pred_ui_track_adjust_from_setpoints(void)
{
  // Capture external (Python/manual) as well as MK3-local adjustments.
  const float cur_r = extruder_rpm_set;
  const int cur_t = (int)(degTargetHotend(0) + 0.5f);

  if (!fr3d_pred_ui_track_inited) {
    fr3d_pred_ui_prev_r = cur_r;
    fr3d_pred_ui_prev_t = cur_t;
    fr3d_pred_ui_track_inited = 1;
    return;
  }

  const float dr = cur_r - fr3d_pred_ui_prev_r;
  const int dt = cur_t - fr3d_pred_ui_prev_t;
  const bool changed_t = (dt != 0);
  const bool changed_r = (fr3d_absf(dr) >= 0.005f);

  if (changed_t) {
    fr3d_pred_ui_last_axis_char = 'T';
    fr3d_pred_ui_last_sign_char = (dt > 0) ? '+' : '-';
    fr3d_pred_ui_last_value = (float)cur_t;
    fr3d_pred_ui_last_value_valid = 1;
  } else if (changed_r) {
    fr3d_pred_ui_last_axis_char = 'E';
    fr3d_pred_ui_last_sign_char = (dr > 0.0f) ? '+' : '-';
    fr3d_pred_ui_last_value = cur_r;
    fr3d_pred_ui_last_value_valid = 1;
  }

  fr3d_pred_ui_prev_r = cur_r;
  fr3d_pred_ui_prev_t = cur_t;
}

static void fr3d_predictor_apply_10s(void)
{
  /* Contrato:
   * - Corrección por Ø (fuera de banda): T + RPM sinfín (E). No mueve pulling.
   * - Optimizar ON + cerca de banda: busca P* (eficiencia observada en PAUT) con pasos E+T.
   *   PULL permanece en Auto: el lazo de tiraje es quien hace subir/bajar P. */
  fr3d_pred_ui_clear();
  if (fr3d_pred_enabled == 0) {
    fr3d_pred_ui_set_idle(' ');
    fr3d_pred_set_pair("Predictor MK3 deshabilitado", "PREDEN=0");
    return;
  }

  if (fr3d_diam_src != 0) {
    if (!fr3d_diam_host_fresh()) {
      fr3d_pred_ui_set_idle('N');
      fr3d_pred_set_pair("Sin accion predictor", "Faltan muestras de diametro (HOST)");
      return;
    }
  } else {
    // Hall A3 local: DH + CALV.
#if defined(FR3D_HALL_DIAMETER_PIN) && (FR3D_HALL_DIAMETER_PIN > -1)
    if (fr3d_hall_diameter_enabled == 0) {
      fr3d_pred_ui_set_idle('O'); /* AO: Hall deshabilitado (DH=0) — distinto de AC */
      fr3d_pred_set_pair("Sin accion predictor", "Hall A3 deshabilitado (DH=0)");
      return;
    }
    if (fr3d_hall_cal_valid == 0) {
      fr3d_pred_ui_set_idle('C'); /* AC: CALV=0 */
      fr3d_pred_set_pair("Sin accion predictor", "Sensor diametro sin calibrar (CALV=0)");
      return;
    }
#else
    fr3d_pred_ui_set_idle('O');
    fr3d_pred_set_pair("Sin accion predictor", "Hall A3 no disponible");
    return;
#endif
  }

  // Equivalente al gate "all green" del asistente Python:
  // - ES=1 y estado RUN (hot + switch)
  // - datos de temperatura válidos y en ventana |Tact-Ttgt|
  // - diámetro medio disponible del último tramo 10 s
  const bool es1_ok = (extrude_status & ES_ENABLE_SET) != 0;
  const bool run_state_ok = ((extrude_status & ES_HOT_SET) != 0) && ((extrude_status & ES_SWITCH_SET) != 0);
  /* Ø y Optimizar exigen PAUT: P es métrica; el Auto de tiraje es la magia del lazo. */
  const bool pull_auto_ok = (extrude_status & ES_AUTO_SET) != 0;
  if (!es1_ok || !run_state_ok || !pull_auto_ok) {
    fr3d_pred_ui_set_idle('G'); /* AG: gate ES/RUN/PULL_AUTO */
    fr3d_pred_set_pair("Sin accion predictor", "Gate: ES/RUN/PULL no cumplido");
    return;
  }

  const float t_act = degHotend(0);
  const float t_tgt = degTargetHotend(0);
  if (!(t_act >= 0.0f && t_tgt >= 0.0f)) {
    fr3d_pred_ui_set_idle('G');
    fr3d_pred_set_pair("Sin accion predictor", "Temperaturas invalidas");
    return;
  }
  if (fr3d_absf(t_act - t_tgt) > fr3d_pred_temp_match_max_c) {
    fr3d_pred_ui_set_idle('G');
    fr3d_pred_set_pair("Sin accion predictor", "Tact/Ttgt fuera de ventana");
    return;
  }

  float d_mean = 0.0f;
  float d_span = 0.0f;
  if (!fr3d_diam_for_pred(&d_mean, &d_span)) {
    fr3d_pred_ui_set_idle('N');
    fr3d_pred_set_pair("Sin accion predictor", "Faltan muestras de diametro");
    return;
  }

  fr3d_pred_fusion_id++;

  const float tgt = fr3d_pred_target_diam_mm;
  const float band_lo = tgt - fr3d_pred_deadband_half_mm;
  const float band_hi = tgt + fr3d_pred_deadband_half_mm;
  const float slack = max(0.0f, FR3D_PRED_OPT_BAND_SLACK_MM);
  const float soft_lo = band_lo - slack;
  const float soft_hi = band_hi + slack;
  const bool in_band = (d_mean >= band_lo && d_mean <= band_hi);
  const bool in_soft_band = (d_mean >= soft_lo && d_mean <= soft_hi);
  /* Con Optimizar+P*: la holgura evita resetear el dwell por un leve sobrepaso. */
  const bool dwell_band =
      (fr3d_pred_optimize && fr3d_pred_p_star_valid) ? in_soft_band : in_band;
  if (dwell_band) {
    if (fr3d_pred_in_band_since_ms == 0UL)
      fr3d_pred_in_band_since_ms = millis();
  } else {
    fr3d_pred_in_band_since_ms = 0UL;
  }
  const uint8_t opt_dwell_ok =
      (fr3d_pred_in_band_since_ms != 0UL) &&
      ((millis() - fr3d_pred_in_band_since_ms) >= FR3D_PRED_OPT_DWELL_MS);
  const float cur_e = extruder_rpm_set;
  const int cur_t = (int)(degTargetHotend(0) + 0.5f);
  const float cur_p = fr3d_pred_pull_rpm();
  const uint8_t freeze_on = fr3d_pred_freeze_active();
  const bool regime_ok = (starttime != 0) && ((millis() - starttime) >= FR3D_PRED_REGIME_MS);

  int16_t t_lo = fr3d_pred_t_min;
  int16_t t_hi = fr3d_pred_t_max;
  if (t_lo > t_hi) { const int16_t tmp = t_lo; t_lo = t_hi; t_hi = tmp; }
  float r_lo = fr3d_pred_r_min;
  float r_hi = fr3d_pred_r_max;
  if (r_lo > r_hi) { const float tmp = r_lo; r_lo = r_hi; r_hi = tmp; }

  if (regime_ok) {
    if (!fr3d_pred_ep_inited) {
      fr3d_pred_ep_reset(cur_e, cur_p);
    } else {
      const float dE = cur_e - fr3d_pred_ep_e0;
      const float dP = cur_p - fr3d_pred_ep_p0;
      const float dE_abs = (dE >= 0.0f) ? dE : -dE;
      const float dP_abs = (dP >= 0.0f) ? dP : -dP;
      const bool e_sig = (dE_abs >= FR3D_PRED_EP_DE_SIG);
      const bool p_followed = (dP_abs >= FR3D_PRED_EP_DP_FLAT);
      fr3d_pred_ep_e_up = (dE >= FR3D_PRED_EP_DE_SIG) ? 1 : 0;
      if (e_sig && p_followed) {
        /* E cambió ≥2 y P también: acoplado. Nueva referencia. */
        fr3d_pred_ep_reset(cur_e, cur_p);
      } else if (e_sig) {
        if (fr3d_pred_ep_dead_since_ms == 0UL)
          fr3d_pred_ep_dead_since_ms = millis();
        fr3d_pred_ep_dead =
            ((millis() - fr3d_pred_ep_dead_since_ms) >= FR3D_PRED_EP_PERSIST_MS) ? 1 : 0;
      } else {
        /* |ΔE|<2: aún no es zona problema. No mover la referencia (acumula). */
        fr3d_pred_ep_dead = 0;
        fr3d_pred_ep_dead_since_ms = 0;
      }
    }
  } else {
    fr3d_pred_ep_inited = 0;
    fr3d_pred_ep_dead = 0;
    fr3d_pred_ep_dead_since_ms = 0;
  }

  if (fr3d_pred_opt_acted_last) {
    if (!in_soft_band) {
      if (fr3d_pred_opt_diam_out_streak < 255) fr3d_pred_opt_diam_out_streak++;
      if (fr3d_pred_opt_diam_out_streak >= (uint8_t)FR3D_PRED_OPT_ABORT_DIAM_STREAK)
        fr3d_pred_begin_freeze();
    } else {
      fr3d_pred_opt_diam_out_streak = 0;
    }
    fr3d_pred_opt_acted_last = 0;
  }

  uint8_t health_warn = 0;
  char health_warn_c = ' ';
  if (regime_ok && fr3d_pred_mode == 1 && fr3d_pred_ep_dead) {
    const int t_mid = ((int)t_lo + (int)t_hi) / 2;
    const bool slip = (cur_t >= t_mid);
    const bool e_up = (fr3d_pred_ep_e_up != 0);
    if (fr3d_pred_optimize == 0) {
      /* Optimizar OFF: solo aviso, no tocar E/T. */
      health_warn = 1;
      health_warn_c = slip ? 'P' : 'U';
    } else {
    int next_t = cur_t;
    float next_e = cur_e;
    if (slip) {
      if (e_up)
        next_e = max(r_lo, cur_e - FR3D_PRED_EP_CORRECT_E);
      if (d_mean <= tgt)
        next_t = max((int)t_lo, cur_t - 2);
      else if (cur_t > (int)t_lo)
        next_t = cur_t - 1;
      fr3d_pred_ui_set_idle('P');
      fr3d_pred_set_pair(
          "Patinaje: salida (90 s)",
          e_up ? "E subio >=2 rpm y P no siguio" : "E bajo >=2 rpm y P no siguio");
    } else {
      next_t = min((int)t_hi, cur_t + 2);
      if (e_up && d_mean < band_lo)
        next_e = max(r_lo, cur_e - FR3D_PRED_EP_CORRECT_E);
      fr3d_pred_ui_set_idle('U');
      fr3d_pred_set_pair(
          "No fusion: salida (90 s)",
          e_up ? "E subio >=2 rpm y P no siguio (T baja)" : "E bajo >=2 rpm y P no siguio (T baja)");
    }
    bool chg = false;
    if (fr3d_absf(next_e - cur_e) >= 0.001f) {
      fr3d_pred_apply_e(next_e);
      chg = true;
    }
    if (next_t != cur_t) {
      setTargetHotend0(next_t);
      fr3d_pred_last_t_change_fusion = (int32_t)fr3d_pred_fusion_id;
      chg = true;
    }
    if (chg) fr3d_pred_mark_transport_hold();
    fr3d_pred_begin_freeze();
    fr3d_pred_ep_reset(extruder_rpm_set, cur_p);
    return;
    }
  }

  char hold_detail[170];
  hold_detail[0] = 0;
  const uint8_t hold_wait = fr3d_pred_transport_hold_tick(hold_detail, sizeof(hold_detail));

  if (in_soft_band) {
    fr3d_pred_margin_bypass = 0;
    fr3d_pred_margin_corner_streak = 0;
    if (regime_ok) {
      if (!fr3d_pred_p_ref_inited) {
        fr3d_pred_p_ref = cur_p;
        fr3d_pred_p_ref_inited = 1;
      } else {
        fr3d_pred_p_ref = 0.85f * fr3d_pred_p_ref + 0.15f * cur_p;
      }
    }
    /* P* vacío (valid=0): no buscar eficiencia; no sembrar con P act. */
    char detail[170];
    if (hold_wait) {
      fr3d_pred_ui_set_idle('H');
      fr3d_pred_set_pair("Optimizar: espera transporte", hold_detail[0] ? hold_detail : "Hold transporte");
      return;
    }
    if (fr3d_pred_p_star_valid)
      snprintf(detail, sizeof(detail), "d=%.3f banda[%.3f..%.3f] P=%.1f P*=%.1f E=%.2f src=%s", d_mean, band_lo, band_hi, cur_p, fr3d_pred_p_star, cur_e,
               (fr3d_diam_src == 2) ? "MAN" : ((fr3d_diam_src == 1) ? "USB" : "A3"));
    else
      snprintf(detail, sizeof(detail), "d=%.3f banda[%.3f..%.3f] P=%.1f P*=- E=%.2f src=%s", d_mean, band_lo, band_hi, cur_p, cur_e,
               (fr3d_diam_src == 2) ? "MAN" : ((fr3d_diam_src == 1) ? "USB" : "A3"));

    if (fr3d_pred_optimize && fr3d_pred_mode == 1 && regime_ok && !freeze_on &&
        opt_dwell_ok && fr3d_pred_p_star_valid) {
      const float p_star = fr3d_pred_p_star;
      float next_e = cur_e;
      int next_t = cur_t;
      const float err_p = cur_p - p_star;
      const bool at_star = (fr3d_absf(err_p) <= FR3D_PRED_P_STAR_EPS);
      if (!at_star) {
        if (cur_p < p_star) {
          /* Subir eficiencia observada: ↑E y ↑T; Auto pull hace subir P. */
          next_e = cur_e + FR3D_PRED_OPT_E_STEP;
          if (next_e > r_hi) next_e = r_hi;
          if (cur_t < (int)t_hi) next_t = cur_t + 1;
        } else {
          /* Bajar eficiencia: ↓E y ↓T suave. */
          next_e = cur_e - FR3D_PRED_OPT_E_STEP;
          if (next_e < r_lo) next_e = r_lo;
          if (cur_t > (int)t_lo) next_t = cur_t - 1;
        }
        next_e = constrain(next_e, EXTRUDER_RPM_MIN, EXTRUDER_RPM_MAX);
        next_e = constrain(next_e, r_lo, r_hi);
      }
      bool chg = false;
      const bool chg_e = (fr3d_absf(next_e - cur_e) >= 0.001f);
      const bool chg_t = (next_t != cur_t);
      if (chg_e) {
        fr3d_pred_apply_e(next_e);
        chg = true;
      }
      if (chg_t) {
        setTargetHotend0(next_t);
        fr3d_pred_last_t_change_fusion = (int32_t)fr3d_pred_fusion_id;
        chg = true;
      }
      if (chg) {
        fr3d_pred_mark_transport_hold();
        fr3d_pred_opt_acted_last = 1;
        fr3d_pred_ui_set('A', chg_e, chg_t, next_e - cur_e, next_t - cur_t, next_e, next_t);
        char main_msg[110];
        if (chg_e && chg_t)
          snprintf(main_msg, sizeof(main_msg), "Optimizar: E %.2f->%.2f  T %d->%d", cur_e, next_e, cur_t, next_t);
        else if (chg_e)
          snprintf(main_msg, sizeof(main_msg), "Optimizar: E %.2f->%.2f", cur_e, next_e);
        else
          snprintf(main_msg, sizeof(main_msg), "Optimizar: T %d->%d", cur_t, next_t);
        fr3d_pred_set_pair(main_msg, detail);
        return;
      }
      if (at_star) {
        fr3d_pred_ui_set_idle('B');
        fr3d_pred_set_pair("Optimizar: en P*", detail);
        return;
      }
      fr3d_pred_ui_set_idle('B');
      fr3d_pred_set_pair("Optimizar: E/T en limite", detail);
      return;
    }

    if (health_warn) {
      fr3d_pred_ui_set_idle(health_warn_c);
      if (health_warn_c == 'P')
        fr3d_pred_set_pair("Patinaje (aviso)", "Optimizar OFF: no se corrige E/T");
      else
        fr3d_pred_set_pair("No fusion (aviso)", "Optimizar OFF: no se corrige E/T");
      return;
    }
    /* Leve sobrepaso: no entrar a DIAM_CTRL agresivo; esperar Auto/transporte. */
    if (!in_band && fr3d_pred_optimize && fr3d_pred_p_star_valid && !freeze_on) {
      fr3d_pred_ui_set_idle('B');
      fr3d_pred_set_pair("Optimizar: Ø cerca de banda", detail);
      return;
    }
    if (freeze_on)
      fr3d_pred_ui_set_idle('Z');
    else
      fr3d_pred_ui_set_idle('B');
    if (fr3d_pred_optimize && regime_ok && !opt_dwell_ok && !freeze_on)
      fr3d_pred_set_pair("Optimizar: espera 90 s en banda", detail);
    else if (fr3d_pred_optimize && !fr3d_pred_p_star_valid)
      fr3d_pred_set_pair("Optimizar: sin P* (P act estable)", detail);
    else
      fr3d_pred_set_pair("Sin accion predictor", detail);
    return;
  }

  const float err = fr3d_absf(d_mean - tgt);
  float step_r = fr3d_pred_k_span_r * d_span + fr3d_pred_k_err_r * err;
  const float dr_min = max(0.0001f, fr3d_pred_delta_r_min);
  const float dr_max = max(dr_min, fr3d_pred_delta_r_max);
  step_r = constrain(step_r, dr_min, dr_max);

  float step_t_raw = fr3d_pred_k_span_t * d_span + fr3d_pred_k_err_t * err;
  const float dt_min = max(0.0f, fr3d_pred_delta_t_min);
  const uint8_t dt_cap = constrain(fr3d_pred_delta_t_max, (uint8_t)1, (uint8_t)20);
  step_t_raw = constrain(step_t_raw, dt_min, (float)dt_cap);
  int step_t = (step_t_raw < 0.5f) ? 0 : (int)(step_t_raw + 0.5f);
  if (step_t < 0) step_t = 0;
  if (step_t > (int)dt_cap) step_t = (int)dt_cap;

  const int32_t age_t = (int32_t)fr3d_pred_fusion_id - fr3d_pred_last_t_change_fusion;
  if (fr3d_pred_t_settle_fusions > 0 &&
      fr3d_pred_last_t_change_fusion > -1000000000L &&
      age_t < (int32_t)fr3d_pred_t_settle_fusions) {
    char detail[170];
    snprintf(detail, sizeof(detail), "Settling T activo: %ld/%u", (long)age_t, (unsigned int)fr3d_pred_t_settle_fusions);
    fr3d_pred_ui_set_idle('S'); /* LCD/Flutter: AS */
    fr3d_pred_set_pair("Sin accion predictor", detail);
    return;
  }

  /* Hold de transporte: esperar ΔL (boquilla→sensor) o timeout tras correctivo E/T. */
  if (hold_wait) {
    fr3d_pred_ui_set_idle('H');
    fr3d_pred_set_pair("Sin accion predictor", hold_detail[0] ? hold_detail : "Hold transporte");
    return;
  }

  // PREDRRNG / pasos dR actúan sobre RPM del sinfín (extruder_rpm_set), no sobre el tirador.
  const float cur_r = extruder_rpm_set;
  const float rm_cfg = max(0.0f, fr3d_pred_r_switch_margin);
  const int tm_cfg = (int)fr3d_pred_t_switch_margin;

  if (!fr3d_pred_margin_bypass) {
    const bool thin_corner = (d_mean < band_lo) && (cur_r >= r_hi - rm_cfg) && (cur_t <= t_lo + tm_cfg);
    const bool thick_corner = (d_mean > band_hi) && (cur_r <= r_lo + rm_cfg) && (cur_t >= t_hi - tm_cfg);
    if (thin_corner || thick_corner) {
      fr3d_pred_margin_corner_streak++;
      if (fr3d_pred_margin_corner_streak >= (uint8_t)FR3D_PRED_MARGIN_BYPASS_STREAK) {
        fr3d_pred_margin_bypass = 1;
        fr3d_pred_margin_corner_streak = 0;
      }
    } else
      fr3d_pred_margin_corner_streak = 0;
  }
  const float r_margin = fr3d_pred_margin_bypass ? 0.0f : rm_cfg;
  const int t_margin = fr3d_pred_margin_bypass ? 0 : tm_cfg;

  float next_r = cur_r;
  int next_t = cur_t;

  if (d_mean < band_lo) { // Muy fino: subir E; si E≈máx, bajar T (E y T en sentidos opuestos)
    const bool near_r_high = cur_r >= (r_hi - r_margin);
    float tgt_r = cur_r;
    if (!near_r_high && !(fr3d_pred_ep_dead && fr3d_pred_ep_e_up))
      tgt_r = min(r_hi, cur_r + step_r);
    tgt_r = constrain(tgt_r, EXTRUDER_RPM_MIN, EXTRUDER_RPM_MAX);
    next_r = tgt_r;
    const bool e_up = tgt_r > cur_r + 0.001f;
    if (!e_up && step_t > 0 && (near_r_high || (fr3d_pred_ep_dead && fr3d_pred_ep_e_up)) && cur_t > t_lo)
      next_t = max((int)t_lo, cur_t - step_t);
  }
  else { // Muy grueso: bajar E o subir T
    const bool near_r_low = cur_r <= (r_lo + r_margin);
    const bool near_t_high = cur_t >= (t_hi - t_margin);
    float tgt_r = cur_r;
    if ((!near_r_low) || near_t_high)
      tgt_r = max(r_lo, cur_r - step_r);
    tgt_r = constrain(tgt_r, EXTRUDER_RPM_MIN, EXTRUDER_RPM_MAX);
    next_r = tgt_r;
    const bool e_dn = tgt_r < cur_r - 0.001f;
    if (!e_dn && step_t > 0)
      next_t = min((int)t_hi, cur_t + step_t);
  }

  bool changed_r = false;
  bool changed_t = false;
  if (fr3d_pred_mode == 1) { // Automático: aplica en firmware (solo E+T, ver contrato arriba).
    if (next_r != cur_r) {
      fr3d_pred_apply_e(next_r);
      changed_r = true;
    }
    if (next_t != cur_t) {
      setTargetHotend0(next_t);
      fr3d_pred_last_t_change_fusion = (int32_t)fr3d_pred_fusion_id;
      changed_t = true;
    }
    if (changed_r || changed_t) {
      fr3d_pred_transport_hold_active = 1;
      fr3d_pred_transport_l_ref_mm = extrude_length;
      fr3d_pred_transport_hold_start_ms = millis();
    }
    char main_msg[110];
    char detail[170];
    if (changed_r || changed_t)
      snprintf(main_msg, sizeof(main_msg), "MK3 aplica predictor: E %.2f->%.2f  T %d->%d", cur_r, next_r, cur_t, next_t);
    else
      snprintf(main_msg, sizeof(main_msg), "MK3 predictor sin cambio");
    snprintf(
        detail,
        sizeof(detail),
        "d=%.3f span=%.3f tgt=%.3f stepE=%.3f stepT=%d src=%s%s",
        d_mean,
        d_span,
        tgt,
        step_r,
        step_t,
        (fr3d_diam_src == 2) ? "MAN" : ((fr3d_diam_src == 1) ? "USB" : "A3"),
        fr3d_pred_margin_bypass ? " MARGIN_BYPASS" : "");
    fr3d_pred_set_pair(main_msg, detail);
    fr3d_pred_ui_set('A', changed_r, changed_t, next_r - cur_r, next_t - cur_t, next_r, next_t);
  } else {
    char main_msg[110];
    char detail[170];
    snprintf(main_msg, sizeof(main_msg), "MK3 propone predictor: E %.2f->%.2f  T %d->%d", cur_r, next_r, cur_t, next_t);
    snprintf(
        detail,
        sizeof(detail),
        "d=%.3f span=%.3f tgt=%.3f stepE=%.3f stepT=%d src=%s%s",
        d_mean,
        d_span,
        tgt,
        step_r,
        step_t,
        (fr3d_diam_src == 2) ? "MAN" : ((fr3d_diam_src == 1) ? "USB" : "A3"),
        fr3d_pred_margin_bypass ? " MARGIN_BYPASS" : "");
    fr3d_pred_set_pair(main_msg, detail);
    /* Auto OFF: LCD/Flutter = SIN A (sin tokens E/T). */
    fr3d_pred_ui_set_idle(' ');
  }
}

static float fr3d_hall_adc_to_mm(float adc)
{
  const float *x = fr3d_hall_cal_adc;

  auto lerp_mm = [](float xv, float xa, float xb, float ya, float yb) -> float
  {
    const float den = (xb - xa);
    if (den == 0.0f) return ya;
    return ya + (xv - xa) * ((yb - ya) / den);
  };

  const bool increasing = x[0] < x[FR3D_HALL_CAL_N - 1];
  uint8_t i;
  for (i = 0; i < (FR3D_HALL_CAL_N - 1); i++)
  {
    const float xa = x[i];
    const float xb = x[i + 1];
    const float ya = fr3d_hall_pattern_mm(i);
    const float yb = fr3d_hall_pattern_mm((uint8_t)(i + 1));
    const bool last = (i == (FR3D_HALL_CAL_N - 2));
    if (increasing)
    {
      if (adc <= xb || last)
        return lerp_mm(adc, xa, xb, ya, yb);
    }
    else
    {
      if (adc >= xb || last)
        return lerp_mm(adc, xa, xb, ya, yb);
    }
  }
  return fr3d_hall_pattern_mm(2);
}

static float fr3d_read_hall_diameter_mm(void)
{
#if defined(FR3D_HALL_DIAMETER_PIN) && (FR3D_HALL_DIAMETER_PIN > -1)
  const int raw = (int)fr3d_hall_adc_read_now();
  float mm = fr3d_hall_adc_to_mm((float)raw);
  mm += fr3d_hall_diam_offset_mm;
  if (mm < 1.50f) mm = 1.50f;
  if (mm > 2.20f) mm = 2.20f;
  return mm;
#else
  return current_filwidth;
#endif
}

static float fr3d_get_csv_diameter_mm(void)
{
  /* Un solo Ø: nunca mezclar Hall con USB/Manual. */
  if (fr3d_diam_src == 2)
    return fr3d_host_diam_mm;
  if (fr3d_diam_src == 1) {
    if (fr3d_diam_host_fresh())
      return fr3d_host_diam_mm;
    return 0.0f;
  }
  return fr3d_read_hall_diameter_mm();
}

static uint8_t fr3d_diam_for_pred(float *d_mean, float *d_span)
{
  if (fr3d_diam_src == 2) {
    *d_mean = fr3d_host_diam_mm;
    *d_span = 0.0f;
    return (*d_mean >= 1.0f) ? 1 : 0;
  }
  if (fr3d_diam_src == 1) {
    if (!fr3d_diam_host_fresh())
      return 0;
    if (fr3d_diam_samples_n == 0) {
      *d_mean = fr3d_host_diam_mm;
      *d_span = 0.0f;
      return (*d_mean >= 1.0f) ? 1 : 0;
    }
  } else if (fr3d_diam_samples_n == 0) {
    return 0;
  }
  *d_mean = fr3d_diam_median_10s;
  *d_span = max(0.0f, fr3d_diam_max_10s - fr3d_diam_min_10s);
  return (*d_mean >= 1.0f) ? 1 : 0;
}

static void fr3d_diam_sample(float value)
{
  fr3d_diam_fifo[fr3d_diam_fifo_head] = value;
  fr3d_diam_fifo_head = (uint8_t)((fr3d_diam_fifo_head + 1U) % FR3D_DIAM_FIFO_CAPACITY);
  if (fr3d_diam_samples_n < FR3D_DIAM_FIFO_CAPACITY)
    fr3d_diam_samples_n++;
}

static void fr3d_diam_glitch_filter_reset(float seed_mm)
{
  fr3d_diam_prev_raw_mm = seed_mm;
  fr3d_diam_last_accepted_mm = seed_mm;
}

static void fr3d_diam_try_sample(float raw_mm)
{
  if (raw_mm < 1.0f)
    return;
  /* Filtro 1.50 mm solo Hall A3. USB/Manual no se recortan. */
  if (fr3d_diam_src != 0) {
    if (fr3d_diam_raw_samples_total < 65535U)
      fr3d_diam_raw_samples_total++;
    fr3d_diam_sample(raw_mm);
    fr3d_diam_last_accepted_mm = raw_mm;
    fr3d_diam_prev_raw_mm = raw_mm;
    if (fr3d_diam_accepted_samples_total < 65535U)
      fr3d_diam_accepted_samples_total++;
    return;
  }

  const float k_filament_mm = 1.53f;
  const float k_floor_hi_mm = 1.52f;

  if (fr3d_diam_raw_samples_total < 65535U)
    fr3d_diam_raw_samples_total++;

  bool discard = false;
  if (fr3d_diam_prev_raw_mm > 0.0f)
  {
    if (raw_mm <= k_floor_hi_mm && fr3d_diam_last_accepted_mm > k_filament_mm && fr3d_diam_prev_raw_mm > k_filament_mm)
      discard = true;
  }
  if (!discard)
  {
    fr3d_diam_sample(raw_mm);
    fr3d_diam_last_accepted_mm = raw_mm;
    if (fr3d_diam_accepted_samples_total < 65535U)
      fr3d_diam_accepted_samples_total++;
  }
  else if (fr3d_diam_drop_floor_total < 65535U)
  {
    fr3d_diam_drop_floor_total++;
  }
  fr3d_diam_prev_raw_mm = raw_mm;
}

static float fr3d_diam_fifo_recent_mm(uint8_t k_back)
{
  // k_back=1 mas reciente, 2 penultima, etc. (buffer circular).
  const uint8_t cap = FR3D_DIAM_FIFO_CAPACITY;
  uint8_t idx;
  if (fr3d_diam_fifo_head >= k_back)
    idx = (uint8_t)(fr3d_diam_fifo_head - k_back);
  else
    idx = (uint8_t)(cap + fr3d_diam_fifo_head - k_back);
  return fr3d_diam_fifo[idx];
}

static void fr3d_diam_recompute_fifo_avg(void)
{
  if (fr3d_diam_samples_n == 0)
  {
    /* Sin muestras: 0 = no hay dato (no usar 1.75 default ni Hall suelto). */
    fr3d_diam_fifo_avg_x1000 = 0;
    return;
  }
  if (fr3d_diam_samples_n == 1)
  {
    fr3d_diam_fifo_avg_x1000 = fr3d_quantize_mm_x1000(fr3d_diam_fifo_recent_mm(1));
    return;
  }
  const float newest = fr3d_diam_fifo_recent_mm(1);
  const float prev = fr3d_diam_fifo_recent_mm(2);
  const float med2 = 0.5f * (newest + prev);
  fr3d_diam_fifo_avg_x1000 = fr3d_quantize_mm_x1000(med2);
}

static void fr3d_diam_window_reset(float seed_value, unsigned long now)
{
  fr3d_diam_glitch_filter_reset(seed_value);
  fr3d_diam_median_debounce_reset(seed_value);
  fr3d_diam_fifo_head = 0;
  fr3d_diam_samples_n = 0;
  fr3d_diam_drop_floor_total = 0;
  fr3d_diam_drop_floor_last_csv = 0;
  fr3d_diam_jump_hold_since_csv = 0;
  fr3d_diam_raw_samples_total = 0;
  fr3d_diam_raw_samples_last_csv = 0;
  fr3d_diam_accepted_samples_total = 0;
  fr3d_diam_accepted_samples_last_csv = 0;
  fr3d_diam_med_raw_last_10s = seed_value;
  fr3d_diam_next_sample_ms = now + FR3D_DIAM_SAMPLE_MS;
  fr3d_diam_recompute_fifo_avg();
}

static void fr3d_diam_accumulate_until(unsigned long now)
{
  while ((long)(now - fr3d_diam_next_sample_ms) >= 0)
  {
    if (fr3d_diam_src == 1 && !fr3d_diam_host_fresh()) {
      /* Gateway/USB cortado: no seguir prediciendo con Ø viejo ni mezclar Hall A3. */
      fr3d_diam_samples_n = 0;
      fr3d_diam_next_sample_ms += FR3D_DIAM_SAMPLE_MS;
      continue;
    }
    fr3d_diam_try_sample(fr3d_get_csv_diameter_mm());
    fr3d_diam_next_sample_ms += FR3D_DIAM_SAMPLE_MS;
  }
  fr3d_diam_recompute_fifo_avg();
}

void fr3d_diam_poll_samples(void)
{
  fr3d_diam_accumulate_until(millis());
}

static void fr3d_diam_close_10s_window(unsigned long now)
{
  fr3d_diam_accumulate_until(now);
  if (fr3d_diam_samples_n > 0)
  {
    float sum = 0.0f;
    float vmin = fr3d_diam_fifo[0];
    float vmax = fr3d_diam_fifo[0];
    for (uint8_t i = 0; i < fr3d_diam_samples_n; ++i)
    {
      const float v = fr3d_diam_fifo[i];
      sum += v;
      if (v < vmin) vmin = v;
      if (v > vmax) vmax = v;
    }
    fr3d_diam_prom_10s = sum / (float)fr3d_diam_samples_n;
    fr3d_diam_min_10s = vmin;
    fr3d_diam_max_10s = vmax;
  }
  else
  {
    // No valid samples available in FIFO yet.
    fr3d_diam_prom_10s = 0.0f;
    fr3d_diam_min_10s = 0.0f;
    fr3d_diam_max_10s = 0.0f;
  }
  fr3d_update_median_10s();
  // Unify around median as central metric across predictor/CSV/LCD.
  fr3d_diam_prom_10s = fr3d_diam_median_10s;
}

static void fr3d_print_sanitized(const char *s)
{
  for (; *s; ++s)
    MYSERIAL.print(*s == ',' ? ';' : *s);
}

static void fr3d_print_csv_escaped(const char *s)
{
  if (!s) s = "";
  MYSERIAL.print('"');
  for (; *s; ++s)
  {
    const char c = *s;
    if (c == '"')
      MYSERIAL.print(F("\"\""));
    else if (c == '\r' || c == '\n')
      MYSERIAL.print(' ');
    else
      MYSERIAL.print(c);
  }
  MYSERIAL.print('"');
}

static void fr3d_print_t_index(uint32_t seq)
{
  MYSERIAL.print('T');
  if (seq <= 999u)
  {
    if (seq < 100u)  MYSERIAL.print('0');
    if (seq < 10u)   MYSERIAL.print('0');
    MYSERIAL.print((unsigned int)seq);
  }
  else
    MYSERIAL.print((unsigned long)seq);
}

static void fr3d_print_e_state(void)
{
  if ((extrude_status & ES_SWITCH_SET) && (extrude_status & ES_HOT_SET))
    MYSERIAL.print(F("RUN"));
  else if (extrude_status & ES_HOT_SET)
    MYSERIAL.print(F("OFF"));
  else
    MYSERIAL.print(F("COLD"));
}

static void fr3d_print_pull_mode(void)
{
  if (extrude_status & ES_AUTO_SET)
    MYSERIAL.print(F("AUTO"));
  else
    MYSERIAL.print(F("MANUAL"));
}

static void fr3d_print_sinfin_csv(void)
{
  if (sinfin_compression_mode == SINFIN_COMP_BAJA)
    MYSERIAL.print(F("BAJA"));
  else
    MYSERIAL.print(F("ALTA"));
}

/** Textos de listas (mismos criterios que menus / EEPROM); sin comas (CSV).
 *  Columna servos: placeholder "-" (mezclador solo STM32 AddonFR3D). */
static void fr3d_print_csv_header(void)
{
  MYSERIAL.print(F("FR3D,T,t_act,t_tgt,E_state,S_w,diam_prom_mm,diam_max_mm,diam_min_mm,ext_rpm,pull_rpm,L_m,status,fan_pct,pull_mode,sinfin,corr_drop_n,corr_jump_hold"));
  if (fr3d_diam_debug_csv_enabled)
    MYSERIAL.print(F(",fifo_n_used,fifo_n_raw,med_raw_mm,med_pub_mm,jump_pending_mm"));
  MYSERIAL.println(F(",servos"));
}

static void fr3d_print_csv_row(uint32_t seq)
{
  const int t_act = (int)(degHotend(0) + 0.5f);
  const int t_tgt = (int)(degTargetHotend(0) + 0.5f);
  const float pull_rpm = puller_feedrate * (60.0f / pcirc);
  const float L_m = extrude_length / 1000.0f;
  uint16_t corr_drop_n = (uint16_t)(fr3d_diam_drop_floor_total - fr3d_diam_drop_floor_last_csv);
  fr3d_diam_drop_floor_last_csv = fr3d_diam_drop_floor_total;
  uint16_t fifo_n_used = (uint16_t)(fr3d_diam_accepted_samples_total - fr3d_diam_accepted_samples_last_csv);
  fr3d_diam_accepted_samples_last_csv = fr3d_diam_accepted_samples_total;
  uint16_t fifo_n_raw = (uint16_t)(fr3d_diam_raw_samples_total - fr3d_diam_raw_samples_last_csv);
  fr3d_diam_raw_samples_last_csv = fr3d_diam_raw_samples_total;
  const uint8_t corr_jump_hold = fr3d_diam_jump_hold_since_csv;
  fr3d_diam_jump_hold_since_csv = 0;
  MYSERIAL.print(F("FR3D,"));
  fr3d_print_t_index(seq);
  MYSERIAL.print(',');
  MYSERIAL.print(t_act);
  MYSERIAL.print(',');
  MYSERIAL.print(t_tgt);
  MYSERIAL.print(',');
  fr3d_print_e_state();
  MYSERIAL.print(',');
  // Keep legacy meaning of S_w (existing MK3 sensor path / current_filwidth).
  MYSERIAL.print(current_filwidth, 3);
  MYSERIAL.print(',');
  MYSERIAL.print(fr3d_diam_prom_10s, 3);
  MYSERIAL.print(',');
  MYSERIAL.print(fr3d_diam_max_10s, 3);
  MYSERIAL.print(',');
  MYSERIAL.print(fr3d_diam_min_10s, 3);
  MYSERIAL.print(',');
  MYSERIAL.print(extruder_rpm, 2);
  MYSERIAL.print(',');
  MYSERIAL.print(pull_rpm, 2);
  MYSERIAL.print(',');
  MYSERIAL.print(L_m, 3);
  MYSERIAL.print(',');
  fr3d_print_sanitized(lcd_status_message);
  MYSERIAL.print(',');
  MYSERIAL.print(default_winder_speed);
  MYSERIAL.print(',');
  fr3d_print_pull_mode();
  MYSERIAL.print(',');
  fr3d_print_sinfin_csv();
  MYSERIAL.print(',');
  MYSERIAL.print((unsigned int)corr_drop_n);
  MYSERIAL.print(',');
  MYSERIAL.print((unsigned int)corr_jump_hold);
  MYSERIAL.print(',');
  if (fr3d_diam_debug_csv_enabled)
  {
    MYSERIAL.print((unsigned int)fifo_n_used);
    MYSERIAL.print(',');
    MYSERIAL.print((unsigned int)fifo_n_raw);
    MYSERIAL.print(',');
    MYSERIAL.print(fr3d_diam_med_raw_last_10s, 3);
    MYSERIAL.print(',');
    MYSERIAL.print(fr3d_diam_median_10s, 3);
    MYSERIAL.print(',');
    if (fr3d_diam_median_pending_n > 0)
      MYSERIAL.print(fr3d_diam_median_pending_mm, 3);
    else
      MYSERIAL.print(F("-"));
    MYSERIAL.print(',');
  }
  MYSERIAL.print(F("-"));
  MYSERIAL.println();
}

void fr3d_csv_request_usb_row(void)
{
  fr3d_csv_usb_emit_pending = 1;
}

static void fr3d_csv_emit_usb_if_pending(void)
{
  if (!fr3d_csv_usb_emit_pending)
    return;
  fr3d_csv_usb_emit_pending = 0;
  if (!fr3d_csv_header_sent)
  {
    fr3d_print_csv_header();
    fr3d_csv_header_sent = 1;
  }
  if (fr3d_csv_seq == 0)
    fr3d_csv_seq = 1;
  fr3d_print_csv_row(fr3d_csv_seq);
}

void fr3d_csv_telemetry_poll(void)
{
  const unsigned long now = millis();
  // Keep LCD predictor tail aligned with current setpoints (not only 10 s CSV ticks).
  fr3d_pred_ui_track_adjust_from_setpoints();

  if (!fr3d_csv_inited)
  {
    const float seed = fr3d_get_csv_diameter_mm();
    fr3d_diam_prom_10s = seed;
    fr3d_diam_min_10s = seed;
    fr3d_diam_max_10s = seed;
    fr3d_diam_window_reset(seed, now);
    fr3d_csv_inited = true;
    fr3d_csv_seq = 0;
    fr3d_csv_next_ms = now + fr3d_csv_period_ms();
    // USB CSV solo bajo demanda (CSVQ); no empujar cabecera/fila al arranque.
    fr3d_csv_emit_usb_if_pending();
    return;
  }

  fr3d_diam_accumulate_until(now);

  if ((long)(now - fr3d_csv_next_ms) >= 0)
  {
    fr3d_diam_close_10s_window(now);
    fr3d_predictor_apply_10s();
    fr3d_csv_seq++;
    fr3d_csv_next_ms += fr3d_csv_period_ms();
    if ((long)(now - fr3d_csv_next_ms) >= 0)
      fr3d_csv_next_ms = now + fr3d_csv_period_ms();
  }

  fr3d_csv_emit_usb_if_pending();
}

void fr3d_csv_sync_sample_timer(void)
{
  const unsigned long now = millis();
  fr3d_csv_next_ms = now + fr3d_csv_period_ms();
  fr3d_diam_window_reset(fr3d_get_csv_diameter_mm(), now);
}

#endif /* ULTRA_LCD */

#endif /* FR3D_CSV_TELEMETRY */
