/*
  FR3D USB CSV telemetry (instantaneous snapshot every 10 s, Model A boot).
*/

#include "Configuration.h"

#ifdef FR3D_CSV_TELEMETRY

#if !defined(ULTRA_LCD)
void fr3d_csv_telemetry_poll(void) {}
void fr3d_csv_sync_sample_timer(void) {}
void fr3d_diam_poll_samples(void) {}
uint16_t fr3d_diam_fifo_avg_x1000 = 0;
#else

uint16_t fr3d_diam_fifo_avg_x1000 = 0;

#include "MK3.h"
#include "temperature.h"
#include "ultralcd.h"
#include <Arduino.h>
#include <stdio.h>

#define FR3D_DIAM_SAMPLE_MS 500UL
#define FR3D_DIAM_FIFO_CAPACITY 20U

static unsigned long fr3d_csv_period_ms(void)
{
  return (unsigned long)((fr3d_csv_cycle_s == 5) ? 5UL : 10UL) * 1000UL;
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

static void fr3d_pred_ui_set(char mode_c, bool changed_r, bool changed_t, float dr, int dt, float next_r, int next_t)
{
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
  /* Contrato: corrección por diámetro solo ajusta T y RPM del sinfín (extruder_rpm_set).
   * No asignar nunca puller_feedrate / puller_feedrate_default aquí: el tirador lo controlan
   * PAUT/lazo automático de pulling u órdenes PR en manual, no este predictor. */
  fr3d_pred_ui_clear();
  if (fr3d_pred_enabled == 0) {
    fr3d_pred_set_pair("Predictor MK3 deshabilitado", "PREDEN=0");
    return;
  }

  // Regla de oro: MK3 predictor solo si el medidor de diámetro local (Hall A3) está habilitado.
#if defined(FR3D_HALL_DIAMETER_PIN) && (FR3D_HALL_DIAMETER_PIN > -1)
  if (fr3d_hall_diameter_enabled == 0) {
    fr3d_pred_set_pair("Sin accion predictor", "Hall A3 deshabilitado (DH=0)");
    return;
  }
#else
  fr3d_pred_set_pair("Sin accion predictor", "Hall A3 no disponible");
  return;
#endif

  // Equivalente al gate "all green" del asistente Python:
  // - ES=1 y estado RUN (hot + switch)
  // - datos de temperatura válidos y en ventana |Tact-Ttgt|
  // - diámetro medio disponible del último tramo 10 s
  const bool es1_ok = (extrude_status & ES_ENABLE_SET) != 0;
  const bool run_state_ok = ((extrude_status & ES_HOT_SET) != 0) && ((extrude_status & ES_SWITCH_SET) != 0);
  const bool pull_auto_ok = (extrude_status & ES_AUTO_SET) != 0;
  if (!es1_ok || !run_state_ok || !pull_auto_ok) {
    fr3d_pred_set_pair("Sin accion predictor", "Gate: ES/RUN/PULL_AUTO no cumplido");
    return;
  }

  const float t_act = degHotend(0);
  const float t_tgt = degTargetHotend(0);
  if (!(t_act >= 0.0f && t_tgt >= 0.0f)) {
    fr3d_pred_set_pair("Sin accion predictor", "Temperaturas invalidas");
    return;
  }
  if (fr3d_absf(t_act - t_tgt) > fr3d_pred_temp_match_max_c) {
    fr3d_pred_set_pair("Sin accion predictor", "Tact/Ttgt fuera de ventana");
    return;
  }

  if (fr3d_diam_samples_n == 0) {
    fr3d_pred_set_pair("Sin accion predictor", "Sin datos de diametro en ventana");
    return;
  }

  fr3d_pred_fusion_id++;

  const float d_mean = fr3d_diam_median_10s;
  const float d_span = max(0.0f, fr3d_diam_max_10s - fr3d_diam_min_10s);
  const float tgt = fr3d_pred_target_diam_mm;
  const float band_lo = tgt - fr3d_pred_deadband_half_mm;
  const float band_hi = tgt + fr3d_pred_deadband_half_mm;
  if (d_mean >= band_lo && d_mean <= band_hi) {
    fr3d_pred_margin_bypass = 0;
    fr3d_pred_margin_corner_streak = 0;
    char detail[170];
    snprintf(detail, sizeof(detail), "d=%.3f en banda [%.3f..%.3f]", d_mean, band_lo, band_hi);
    fr3d_pred_set_pair("Sin accion predictor", detail);
    return;
  }

  int16_t t_lo = fr3d_pred_t_min;
  int16_t t_hi = fr3d_pred_t_max;
  if (t_lo > t_hi) { const int16_t tmp = t_lo; t_lo = t_hi; t_hi = tmp; }

  float r_lo = fr3d_pred_r_min;
  float r_hi = fr3d_pred_r_max;
  if (r_lo > r_hi) { const float tmp = r_lo; r_lo = r_hi; r_hi = tmp; }

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
    fr3d_pred_set_pair("Sin accion predictor", detail);
    return;
  }

  // PREDRRNG / pasos dR actúan sobre RPM del sinfín (extruder_rpm_set), no sobre el tirador.
  const float cur_r = extruder_rpm_set;
  const int cur_t = (int)(degTargetHotend(0) + 0.5f);
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
    if (!near_r_high)
      tgt_r = min(r_hi, cur_r + step_r);
    tgt_r = constrain(tgt_r, EXTRUDER_RPM_MIN, EXTRUDER_RPM_MAX);
    next_r = tgt_r;
    const bool e_up = tgt_r > cur_r + 0.001f;
    if (!e_up && step_t > 0 && near_r_high && cur_t > t_lo)
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
      extruder_rpm_set = next_r;
      changed_r = true;
    }
    if (next_t != cur_t) {
      setTargetHotend0(next_t);
      fr3d_pred_last_t_change_fusion = (int32_t)fr3d_pred_fusion_id;
      changed_t = true;
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
        "d=%.3f span=%.3f tgt=%.3f stepE=%.3f stepT=%d%s",
        d_mean,
        d_span,
        tgt,
        step_r,
        step_t,
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
        "d=%.3f span=%.3f tgt=%.3f stepE=%.3f stepT=%d%s",
        d_mean,
        d_span,
        tgt,
        step_r,
        step_t,
        fr3d_pred_margin_bypass ? " MARGIN_BYPASS" : "");
    fr3d_pred_set_pair(main_msg, detail);
    changed_r = (next_r != cur_r);
    changed_t = (next_t != cur_t);
    fr3d_pred_ui_set('M', changed_r, changed_t, next_r - cur_r, next_t - cur_t, next_r, next_t);
  }
}

static float fr3d_hall_adc_to_mm(float adc)
{
  const float x1 = fr3d_hall_cal_adc_170;
  const float x2 = fr3d_hall_cal_adc_175;
  const float x3 = fr3d_hall_cal_adc_180;

  // Segment 1.70 -> 1.75
  auto lerp_mm = [](float x, float xa, float xb, float ya, float yb) -> float
  {
    const float den = (xb - xa);
    if (den == 0.0f) return ya;
    return ya + (x - xa) * ((yb - ya) / den);
  };

  // Handle both monotonic directions:
  // - adc increasing with diameter: x1 < x2 < x3
  // - adc decreasing with diameter: x1 > x2 > x3
  const bool first_segment = ((x1 <= x2) && (adc <= x2)) || ((x1 >= x2) && (adc >= x2));
  if (first_segment)
  {
    return lerp_mm(adc, x1, x2, 1.70f, 1.75f);
  }
  // Segment 1.75 -> 1.80
  return lerp_mm(adc, x2, x3, 1.75f, 1.80f);
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
  return fr3d_read_hall_diameter_mm();
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
    fr3d_diam_fifo_avg_x1000 = fr3d_quantize_mm_x1000(fr3d_read_hall_diameter_mm());
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
    fr3d_print_csv_header();
    fr3d_csv_inited = true;
    fr3d_csv_seq = 1;
    fr3d_print_csv_row(fr3d_csv_seq);
    fr3d_csv_next_ms = now + fr3d_csv_period_ms();
    return;
  }

  fr3d_diam_accumulate_until(now);

  if ((long)(now - fr3d_csv_next_ms) < 0)
    return;

  fr3d_diam_close_10s_window(now);
  fr3d_predictor_apply_10s();
  fr3d_csv_seq++;
  fr3d_print_csv_row(fr3d_csv_seq);
  fr3d_csv_next_ms += fr3d_csv_period_ms();
  if ((long)(now - fr3d_csv_next_ms) >= 0)
    fr3d_csv_next_ms = now + fr3d_csv_period_ms();
}

void fr3d_csv_sync_sample_timer(void)
{
  const unsigned long now = millis();
  fr3d_csv_next_ms = now + fr3d_csv_period_ms();
  fr3d_diam_window_reset(fr3d_get_csv_diameter_mm(), now);
}

#endif /* ULTRA_LCD */

#endif /* FR3D_CSV_TELEMETRY */
