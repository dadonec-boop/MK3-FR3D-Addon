#ifndef FR3D_TELEMETRY_H
#define FR3D_TELEMETRY_H

#ifdef FR3D_CSV_TELEMETRY
void fr3d_csv_telemetry_poll(void);
void fr3d_csv_sync_sample_timer(void);
/** Muestreo FIFO 500 ms para LCD (llamar antes de lcd_update). */
void fr3d_diam_poll_samples(void);
/** Mediana de las 2 ultimas muestras FIFO (mm x1000) para LCD campo D y Hall A3. */
extern uint16_t fr3d_diam_fifo_avg_x1000;
extern uint16_t fr3d_pred_median_10s_x1000;
extern char fr3d_pred_ui_mode_char;
extern char fr3d_pred_ui_adjust_char_0;
extern char fr3d_pred_ui_adjust_char_1;
extern char fr3d_pred_ui_sign_char;
extern char fr3d_pred_ui_last_axis_char;
extern char fr3d_pred_ui_last_sign_char;
extern uint8_t fr3d_pred_ui_last_value_valid;
extern float fr3d_pred_ui_last_value;
#else
#define fr3d_csv_telemetry_poll() ((void)0)
#define fr3d_csv_sync_sample_timer() ((void)0)
#define fr3d_diam_poll_samples() ((void)0)
#endif

#endif
