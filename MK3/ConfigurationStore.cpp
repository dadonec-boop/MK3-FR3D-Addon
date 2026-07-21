#include "MK3.h"
#include "planner.h"
#include "temperature.h"
#include "ultralcd.h"
#include "ConfigurationStore.h"

#ifndef DELTA
/* Snapshot solo temperatura E0 (no forma parte del bloque V19; slot fijo en EEPROM). */
#define EEPROM_STANDALONE_HOTEND_ADDR 1010
#define EEPROM_STANDALONE_HOTEND_MAGIC 0xA7

static void hotend_standalone_write(int t)
{
  if (t < 0)
    t = 0;
  int lim = HEATER_0_MAXTEMP - 15;
  if (t > lim)
    t = lim;
  int16_t v = (int16_t)t;
  eeprom_write_byte((uint8_t*)(unsigned)EEPROM_STANDALONE_HOTEND_ADDR, (uint8_t)EEPROM_STANDALONE_HOTEND_MAGIC);
  eeprom_write_byte((uint8_t*)(unsigned)(EEPROM_STANDALONE_HOTEND_ADDR + 1), (uint8_t)(v & 0xFF));
  eeprom_write_byte((uint8_t*)(unsigned)(EEPROM_STANDALONE_HOTEND_ADDR + 2), (uint8_t)((v >> 8) & 0xFF));
}

static int hotend_standalone_read(void)
{
  if (eeprom_read_byte((uint8_t*)(unsigned)EEPROM_STANDALONE_HOTEND_ADDR) != (uint8_t)EEPROM_STANDALONE_HOTEND_MAGIC)
    return 0;
  int16_t v = (int16_t)(
      (uint16_t)eeprom_read_byte((uint8_t*)(unsigned)(EEPROM_STANDALONE_HOTEND_ADDR + 1))
      | ((uint16_t)eeprom_read_byte((uint8_t*)(unsigned)(EEPROM_STANDALONE_HOTEND_ADDR + 2)) << 8));
  if (v < 0 || v > (int16_t)(HEATER_0_MAXTEMP - 15))
    return 0;
  return (int)v;
}

/** Tras leer el bloque principal, restaura objetivo E0 desde el snapshot (guardado con Store). */
static void config_apply_standalone_hotend_after_retrieve(void)
{
  int t = hotend_standalone_read();
  target_temperature[0] = t;
}
#endif

void _EEPROM_writeData(int &pos, uint8_t* value, uint8_t size)
{
    do
    {
        eeprom_write_byte((unsigned char*)pos, *value);
        pos++;
        value++;
    }while(--size);
}
#define EEPROM_WRITE_VAR(pos, value) _EEPROM_writeData(pos, (uint8_t*)&value, sizeof(value))
void _EEPROM_readData(int &pos, uint8_t* value, uint8_t size)
{
    do
    {
        *value = eeprom_read_byte((unsigned char*)pos);
        pos++;
        value++;
    }while(--size);
}
#define EEPROM_READ_VAR(pos, value) _EEPROM_readData(pos, (uint8_t*)&value, sizeof(value))
//======================================================================================

#define EEPROM_OFFSET 100





// IMPORTANT:  Whenever there are changes made to the variables stored in EEPROM
// in the functions below, also increment the version number. This makes sure that
// the default values are used whenever there is a change to the data, to prevent
// wrong data being written to the variables.
// ALSO:  always make sure the variables in the Store and retrieve sections are in the same order.
#ifdef DELTA
#define EEPROM_VERSION "V11"
#else
#define EEPROM_VERSION "V29"
#endif

#ifdef EEPROM_SETTINGS
void Config_StoreSettings() 
{
  char ver[4]= "000";
  int i=EEPROM_OFFSET;
  EEPROM_WRITE_VAR(i,ver); // invalidate data first 
  EEPROM_WRITE_VAR(i,axis_steps_per_unit);  
  EEPROM_WRITE_VAR(i,max_feedrate);  
  EEPROM_WRITE_VAR(i,max_acceleration_units_per_sq_second);
  EEPROM_WRITE_VAR(i,acceleration);
  EEPROM_WRITE_VAR(i,retract_acceleration);
  EEPROM_WRITE_VAR(i,minimumfeedrate);
  EEPROM_WRITE_VAR(i,mintravelfeedrate);
  EEPROM_WRITE_VAR(i,minsegmenttime);
  EEPROM_WRITE_VAR(i,max_xy_jerk);
  EEPROM_WRITE_VAR(i,max_z_jerk);
  EEPROM_WRITE_VAR(i,max_e_jerk);
  EEPROM_WRITE_VAR(i,add_homeing);
  #ifdef DELTA
  EEPROM_WRITE_VAR(i,endstop_adj);
  EEPROM_WRITE_VAR(i,delta_radius);
  EEPROM_WRITE_VAR(i,delta_diagonal_rod);
  EEPROM_WRITE_VAR(i,delta_segments_per_second);
  #endif
  #ifndef ULTIPANEL
  int plaPreheatHotendTemp = PLA_PREHEAT_HOTEND_TEMP, plaPreheatHPBTemp = PLA_PREHEAT_HPB_TEMP, plaPreheatFanSpeed = PLA_PREHEAT_FAN_SPEED;
  int absPreheatHotendTemp = PREHEAT_EXTRUDER_TEMP, absPreheatHPBTemp = ABS_PREHEAT_HPB_TEMP, default_winder_speed = ABS_PREHEAT_FAN_SPEED;
  #endif
  EEPROM_WRITE_VAR(i,plaPreheatHotendTemp);
  EEPROM_WRITE_VAR(i,plaPreheatHPBTemp);
  EEPROM_WRITE_VAR(i,plaPreheatFanSpeed);
  EEPROM_WRITE_VAR(i,absPreheatHotendTemp);
  EEPROM_WRITE_VAR(i,absPreheatHPBTemp);
  EEPROM_WRITE_VAR(i,default_winder_speed);
  EEPROM_WRITE_VAR(i,zprobe_zoffset);
  #ifdef PIDTEMP
    EEPROM_WRITE_VAR(i,Kp);
    EEPROM_WRITE_VAR(i,Ki);
    EEPROM_WRITE_VAR(i,Kd);
  #else
		float dummy = 3000.0f;
    EEPROM_WRITE_VAR(i,dummy);
		dummy = 0.0f;
    EEPROM_WRITE_VAR(i,dummy);
    EEPROM_WRITE_VAR(i,dummy);
  #endif
  #ifndef DOGLCD
    int lcd_contrast = 32;
  #endif
  EEPROM_WRITE_VAR(i,lcd_contrast);
  
  //Lyman Extruder saved items
  EEPROM_WRITE_VAR(i,extruder_rpm_set); //setpoint for extruder RPM
  EEPROM_WRITE_VAR(i,puller_feedrate_default); //puller motor feed rate in mm/sec   
  EEPROM_WRITE_VAR(i,filament_width_desired); //holds the desired filament width (i.e like 2.6mm)
  EEPROM_WRITE_VAR(i,fwidthKp);
  EEPROM_WRITE_VAR(i,fwidthKi);  //removed delta T portion since we will handle explicitily
  EEPROM_WRITE_VAR(i,fwidthKd);
  EEPROM_WRITE_VAR(i,fFactor1);
  EEPROM_WRITE_VAR(i,fFactor2);
  EEPROM_WRITE_VAR(i,fil_length_cutoff); 
  EEPROM_WRITE_VAR(i,winder_rpm_factor);
  EEPROM_WRITE_VAR(i,pcirc);
  EEPROM_WRITE_VAR(i,sensorRunoutMin);
  EEPROM_WRITE_VAR(i,sensorRunoutMax);
  EEPROM_WRITE_VAR(i,fr3d_hall_diameter_enabled);
  EEPROM_WRITE_VAR(i,fr3d_hall_cal_adc_170);
  EEPROM_WRITE_VAR(i,fr3d_hall_cal_adc_175);
  EEPROM_WRITE_VAR(i,fr3d_hall_cal_adc_180);
  EEPROM_WRITE_VAR(i,fr3d_hall_diam_offset_mm);
  EEPROM_WRITE_VAR(i,fr3d_hall_pattern);
  EEPROM_WRITE_VAR(i,fr3d_hall_cal_valid);
  EEPROM_WRITE_VAR(i,fr3d_hall_cal_mask);
  {
    const uint8_t fr3d_pred_owner_eeprom_pad = 1;
    EEPROM_WRITE_VAR(i, fr3d_pred_owner_eeprom_pad);
  }
  EEPROM_WRITE_VAR(i,fr3d_pred_enabled);
  EEPROM_WRITE_VAR(i,fr3d_pred_mode);
  EEPROM_WRITE_VAR(i,fr3d_pred_window_size);
  EEPROM_WRITE_VAR(i,fr3d_pred_target_diam_mm);
  EEPROM_WRITE_VAR(i,fr3d_pred_deadband_half_mm);
  EEPROM_WRITE_VAR(i,fr3d_pred_temp_match_max_c);
  EEPROM_WRITE_VAR(i,fr3d_pred_r_min);
  EEPROM_WRITE_VAR(i,fr3d_pred_r_max);
  EEPROM_WRITE_VAR(i,fr3d_pred_t_min);
  EEPROM_WRITE_VAR(i,fr3d_pred_t_max);
  EEPROM_WRITE_VAR(i,fr3d_pred_delta_r_min);
  EEPROM_WRITE_VAR(i,fr3d_pred_delta_r_max);
  EEPROM_WRITE_VAR(i,fr3d_pred_k_span_r);
  EEPROM_WRITE_VAR(i,fr3d_pred_k_err_r);
  EEPROM_WRITE_VAR(i,fr3d_pred_delta_t_min);
  EEPROM_WRITE_VAR(i,fr3d_pred_delta_t_max);
  EEPROM_WRITE_VAR(i,fr3d_pred_k_span_t);
  EEPROM_WRITE_VAR(i,fr3d_pred_k_err_t);
  EEPROM_WRITE_VAR(i,fr3d_pred_r_switch_margin);
  EEPROM_WRITE_VAR(i,fr3d_pred_t_switch_margin);
  EEPROM_WRITE_VAR(i,fr3d_pred_t_settle_fusions);
  EEPROM_WRITE_VAR(i,fr3d_diam_jump_debounce_mm);
  EEPROM_WRITE_VAR(i,fr3d_diam_pending_match_mm);
  EEPROM_WRITE_VAR(i,fr3d_diam_debug_csv_enabled);
  EEPROM_WRITE_VAR(i,fr3d_csv_cycle_s);
#ifndef DELTA
  EEPROM_WRITE_VAR(i,sinfin_compression_mode);
  #ifdef FR3D_SERIAL_HOST_DISABLE_GM
  fr3d_serial_filter_msgs = true; /* Always ON; not user-visible */
  EEPROM_WRITE_VAR(i,fr3d_serial_filter_msgs);
  #endif
#endif
#ifndef DELTA
  hotend_standalone_write(target_temperature[0]);
#endif

  char ver2[4]=EEPROM_VERSION;
  i=EEPROM_OFFSET;
  EEPROM_WRITE_VAR(i,ver2); // validate data
  SERIAL_ECHO_START;
  SERIAL_ECHOLNPGM("Settings Stored");
}
#endif //EEPROM_SETTINGS


#ifndef DISABLE_M503
void Config_PrintSettings()
{  // Always have this function, even with EEPROM_SETTINGS disabled, the current values will be shown
    SERIAL_ECHO_START;
    SERIAL_ECHOLNPGM("Steps per unit:");
    SERIAL_ECHO_START;
    SERIAL_ECHOPAIR("  M92 X",axis_steps_per_unit[0]);
    SERIAL_ECHOPAIR(" Y",axis_steps_per_unit[1]);
    SERIAL_ECHOPAIR(" Z",axis_steps_per_unit[2]);
    SERIAL_ECHOPAIR(" E",axis_steps_per_unit[3]);
    SERIAL_ECHOLN("");
      
    SERIAL_ECHO_START;
    SERIAL_ECHOLNPGM("Maximum feedrates (mm/s):");
    SERIAL_ECHO_START;
    SERIAL_ECHOPAIR("  M203 X",max_feedrate[0]);
    SERIAL_ECHOPAIR(" Y",max_feedrate[1] ); 
    SERIAL_ECHOPAIR(" Z", max_feedrate[2] ); 
    SERIAL_ECHOPAIR(" E", max_feedrate[3]);
    SERIAL_ECHOLN("");

    SERIAL_ECHO_START;
    SERIAL_ECHOLNPGM("Maximum Acceleration (mm/s2):");
    SERIAL_ECHO_START;
    SERIAL_ECHOPAIR("  M201 X" ,max_acceleration_units_per_sq_second[0] ); 
    SERIAL_ECHOPAIR(" Y" , max_acceleration_units_per_sq_second[1] ); 
    SERIAL_ECHOPAIR(" Z" ,max_acceleration_units_per_sq_second[2] );
    SERIAL_ECHOPAIR(" E" ,max_acceleration_units_per_sq_second[3]);
    SERIAL_ECHOLN("");
    SERIAL_ECHO_START;
    SERIAL_ECHOLNPGM("Acceleration: S=acceleration, T=retract acceleration");
    SERIAL_ECHO_START;
    SERIAL_ECHOPAIR("  M204 S",acceleration ); 
    SERIAL_ECHOPAIR(" T" ,retract_acceleration);
    SERIAL_ECHOLN("");

    SERIAL_ECHO_START;
    SERIAL_ECHOLNPGM("Advanced variables: S=Min feedrate (mm/s), T=Min travel feedrate (mm/s), B=minimum segment time (ms), X=maximum XY jerk (mm/s),  Z=maximum Z jerk (mm/s),  E=maximum E jerk (mm/s)");
    SERIAL_ECHO_START;
    SERIAL_ECHOPAIR("  M205 S",minimumfeedrate ); 
    SERIAL_ECHOPAIR(" T" ,mintravelfeedrate ); 
    SERIAL_ECHOPAIR(" B" ,minsegmenttime ); 
    SERIAL_ECHOPAIR(" X" ,max_xy_jerk ); 
    SERIAL_ECHOPAIR(" Z" ,max_z_jerk);
    SERIAL_ECHOPAIR(" E" ,max_e_jerk);
    SERIAL_ECHOLN(""); 

    SERIAL_ECHO_START;
    SERIAL_ECHOLNPGM("Home offset (mm):");
    SERIAL_ECHO_START;
    SERIAL_ECHOPAIR("  M206 X",add_homeing[0] );
    SERIAL_ECHOPAIR(" Y" ,add_homeing[1] );
    SERIAL_ECHOPAIR(" Z" ,add_homeing[2] );
    SERIAL_ECHOLN("");
#ifdef DELTA
    SERIAL_ECHO_START;
    SERIAL_ECHOLNPGM("Endstop adjustement (mm):");
    SERIAL_ECHO_START;
    SERIAL_ECHOPAIR("  M666 X",endstop_adj[0] );
    SERIAL_ECHOPAIR(" Y" ,endstop_adj[1] );
    SERIAL_ECHOPAIR(" Z" ,endstop_adj[2] );
	SERIAL_ECHOLN("");
	SERIAL_ECHO_START;
	SERIAL_ECHOLNPGM("Delta settings: L=delta_diagonal_rod, R=delta_radius, S=delta_segments_per_second");
	SERIAL_ECHO_START;
	SERIAL_ECHOPAIR("  M665 L",delta_diagonal_rod );
	SERIAL_ECHOPAIR(" R" ,delta_radius );
	SERIAL_ECHOPAIR(" S" ,delta_segments_per_second );
	SERIAL_ECHOLN("");
#endif
#ifdef PIDTEMP
    SERIAL_ECHO_START;
    SERIAL_ECHOLNPGM("PID settings:");
    SERIAL_ECHO_START;
    SERIAL_ECHOPAIR("   M301 P",Kp); 
    SERIAL_ECHOPAIR(" I" ,unscalePID_i(Ki)); 
    SERIAL_ECHOPAIR(" D" ,unscalePID_d(Kd));
    SERIAL_ECHOLN(""); 
#endif
#ifndef DELTA
    SERIAL_ECHO_START;
    SERIAL_ECHOLNPGM("Sinfin (0=alta 1=baja):");
    SERIAL_ECHO_START;
    SERIAL_PROTOCOL((int)sinfin_compression_mode);
    SERIAL_ECHOLN("");
#endif
} 
#endif


#ifdef EEPROM_SETTINGS
#ifndef DELTA
static void eeprom_read_mk3_payload(int &i)
{
        EEPROM_READ_VAR(i,axis_steps_per_unit);
        EEPROM_READ_VAR(i,max_feedrate);
        EEPROM_READ_VAR(i,max_acceleration_units_per_sq_second);
        reset_acceleration_rates();
        EEPROM_READ_VAR(i,acceleration);
        EEPROM_READ_VAR(i,retract_acceleration);
        EEPROM_READ_VAR(i,minimumfeedrate);
        EEPROM_READ_VAR(i,mintravelfeedrate);
        EEPROM_READ_VAR(i,minsegmenttime);
        EEPROM_READ_VAR(i,max_xy_jerk);
        EEPROM_READ_VAR(i,max_z_jerk);
        EEPROM_READ_VAR(i,max_e_jerk);
        EEPROM_READ_VAR(i,add_homeing);
        #ifndef ULTIPANEL
        int plaPreheatHotendTemp, plaPreheatHPBTemp, plaPreheatFanSpeed;
        int absPreheatHotendTemp, absPreheatHPBTemp, default_winder_speed;
        #endif
        EEPROM_READ_VAR(i,plaPreheatHotendTemp);
        EEPROM_READ_VAR(i,plaPreheatHPBTemp);
        EEPROM_READ_VAR(i,plaPreheatFanSpeed);
        EEPROM_READ_VAR(i,absPreheatHotendTemp);
        EEPROM_READ_VAR(i,absPreheatHPBTemp);
        EEPROM_READ_VAR(i,default_winder_speed);
        EEPROM_READ_VAR(i,zprobe_zoffset);
        #ifndef PIDTEMP
        float Kp,Ki,Kd;
        #endif
        EEPROM_READ_VAR(i,Kp);
        EEPROM_READ_VAR(i,Ki);
        EEPROM_READ_VAR(i,Kd);
        #ifndef DOGLCD
        int lcd_contrast;
        #endif
        EEPROM_READ_VAR(i,lcd_contrast);
        EEPROM_READ_VAR(i,extruder_rpm_set);
        EEPROM_READ_VAR(i,puller_feedrate_default);
        EEPROM_READ_VAR(i,filament_width_desired);
        EEPROM_READ_VAR(i,fwidthKp);
        EEPROM_READ_VAR(i,fwidthKi);
        EEPROM_READ_VAR(i,fwidthKd);
        EEPROM_READ_VAR(i,fFactor1);
        EEPROM_READ_VAR(i,fFactor2);
        EEPROM_READ_VAR(i,fil_length_cutoff);
        EEPROM_READ_VAR(i,winder_rpm_factor);
        EEPROM_READ_VAR(i,pcirc);
        EEPROM_READ_VAR(i,sensorRunoutMin);
        EEPROM_READ_VAR(i,sensorRunoutMax);
}
#endif

void Config_RetrieveSettings(bool apply_standalone_hotend)
{
    int i=EEPROM_OFFSET;
    char stored_ver[4];
    bool eeprom_data_loaded = false;
#ifdef DELTA
    char ver[4]=EEPROM_VERSION;
#endif
    EEPROM_READ_VAR(i,stored_ver);
#ifdef DELTA
    if (strncmp(ver,stored_ver,3) == 0)
    {
        EEPROM_READ_VAR(i,axis_steps_per_unit);
        EEPROM_READ_VAR(i,max_feedrate);
        EEPROM_READ_VAR(i,max_acceleration_units_per_sq_second);
        reset_acceleration_rates();
        EEPROM_READ_VAR(i,acceleration);
        EEPROM_READ_VAR(i,retract_acceleration);
        EEPROM_READ_VAR(i,minimumfeedrate);
        EEPROM_READ_VAR(i,mintravelfeedrate);
        EEPROM_READ_VAR(i,minsegmenttime);
        EEPROM_READ_VAR(i,max_xy_jerk);
        EEPROM_READ_VAR(i,max_z_jerk);
        EEPROM_READ_VAR(i,max_e_jerk);
        EEPROM_READ_VAR(i,add_homeing);
        EEPROM_READ_VAR(i,endstop_adj);
        EEPROM_READ_VAR(i,delta_radius);
        EEPROM_READ_VAR(i,delta_diagonal_rod);
        EEPROM_READ_VAR(i,delta_segments_per_second);
        #ifndef ULTIPANEL
        int plaPreheatHotendTemp, plaPreheatHPBTemp, plaPreheatFanSpeed;
        int absPreheatHotendTemp, absPreheatHPBTemp, default_winder_speed;
        #endif
        EEPROM_READ_VAR(i,plaPreheatHotendTemp);
        EEPROM_READ_VAR(i,plaPreheatHPBTemp);
        EEPROM_READ_VAR(i,plaPreheatFanSpeed);
        EEPROM_READ_VAR(i,absPreheatHotendTemp);
        EEPROM_READ_VAR(i,absPreheatHPBTemp);
        EEPROM_READ_VAR(i,default_winder_speed);
        EEPROM_READ_VAR(i,zprobe_zoffset);
        #ifndef PIDTEMP
        float Kp,Ki,Kd;
        #endif
        EEPROM_READ_VAR(i,Kp);
        EEPROM_READ_VAR(i,Ki);
        EEPROM_READ_VAR(i,Kd);
        #ifndef DOGLCD
        int lcd_contrast;
        #endif
        EEPROM_READ_VAR(i,lcd_contrast);
        EEPROM_READ_VAR(i,extruder_rpm_set);
        EEPROM_READ_VAR(i,puller_feedrate_default);
        EEPROM_READ_VAR(i,filament_width_desired);
        EEPROM_READ_VAR(i,fwidthKp);
        EEPROM_READ_VAR(i,fwidthKi);
        EEPROM_READ_VAR(i,fwidthKd);
        EEPROM_READ_VAR(i,fFactor1);
        EEPROM_READ_VAR(i,fFactor2);
        EEPROM_READ_VAR(i,fil_length_cutoff);
        EEPROM_READ_VAR(i,winder_rpm_factor);
        EEPROM_READ_VAR(i,pcirc);
        EEPROM_READ_VAR(i,sensorRunoutMin);
        EEPROM_READ_VAR(i,sensorRunoutMax);
        updatePID();
        eeprom_data_loaded = true;
        SERIAL_ECHO_START;
        SERIAL_ECHOLNPGM("Stored settings retrieved");
    }
    else
    {
        Config_ResetDefault();
    }
#else
    if (strncmp("V29", stored_ver, 3) == 0)
    {
        eeprom_read_mk3_payload(i);
        EEPROM_READ_VAR(i, fr3d_hall_diameter_enabled);
        EEPROM_READ_VAR(i, fr3d_hall_cal_adc_170);
        EEPROM_READ_VAR(i, fr3d_hall_cal_adc_175);
        EEPROM_READ_VAR(i, fr3d_hall_cal_adc_180);
        EEPROM_READ_VAR(i, fr3d_hall_diam_offset_mm);
        EEPROM_READ_VAR(i, fr3d_hall_pattern);
        EEPROM_READ_VAR(i, fr3d_hall_cal_valid);
        EEPROM_READ_VAR(i, fr3d_hall_cal_mask);
        {
          uint8_t fr3d_pred_owner_eeprom_pad = 1;
          EEPROM_READ_VAR(i, fr3d_pred_owner_eeprom_pad);
          (void)fr3d_pred_owner_eeprom_pad;
        }
        EEPROM_READ_VAR(i, fr3d_pred_enabled);
        EEPROM_READ_VAR(i, fr3d_pred_mode);
        EEPROM_READ_VAR(i, fr3d_pred_window_size);
        EEPROM_READ_VAR(i, fr3d_pred_target_diam_mm);
        EEPROM_READ_VAR(i, fr3d_pred_deadband_half_mm);
        EEPROM_READ_VAR(i, fr3d_pred_temp_match_max_c);
        EEPROM_READ_VAR(i, fr3d_pred_r_min);
        EEPROM_READ_VAR(i, fr3d_pred_r_max);
        EEPROM_READ_VAR(i, fr3d_pred_t_min);
        EEPROM_READ_VAR(i, fr3d_pred_t_max);
        EEPROM_READ_VAR(i, fr3d_pred_delta_r_min);
        EEPROM_READ_VAR(i, fr3d_pred_delta_r_max);
        EEPROM_READ_VAR(i, fr3d_pred_k_span_r);
        EEPROM_READ_VAR(i, fr3d_pred_k_err_r);
        EEPROM_READ_VAR(i, fr3d_pred_delta_t_min);
        EEPROM_READ_VAR(i, fr3d_pred_delta_t_max);
        EEPROM_READ_VAR(i, fr3d_pred_k_span_t);
        EEPROM_READ_VAR(i, fr3d_pred_k_err_t);
        EEPROM_READ_VAR(i, fr3d_pred_r_switch_margin);
        EEPROM_READ_VAR(i, fr3d_pred_t_switch_margin);
        EEPROM_READ_VAR(i, fr3d_pred_t_settle_fusions);
        EEPROM_READ_VAR(i, fr3d_diam_jump_debounce_mm);
        EEPROM_READ_VAR(i, fr3d_diam_pending_match_mm);
        EEPROM_READ_VAR(i, fr3d_diam_debug_csv_enabled);
        if (fr3d_diam_jump_debounce_mm < 0.0f) fr3d_diam_jump_debounce_mm = 0.0f;
        else if (fr3d_diam_jump_debounce_mm > 0.5f) fr3d_diam_jump_debounce_mm = 0.5f;
        if (fr3d_diam_pending_match_mm < 0.0f) fr3d_diam_pending_match_mm = 0.0f;
        else if (fr3d_diam_pending_match_mm > 0.2f) fr3d_diam_pending_match_mm = 0.2f;
        if (fr3d_diam_debug_csv_enabled > 1) fr3d_diam_debug_csv_enabled = (uint8_t)FR3D_DIAM_DEBUG_DEFAULT;
        EEPROM_READ_VAR(i, fr3d_csv_cycle_s);
        EEPROM_READ_VAR(i, sinfin_compression_mode);
        #ifdef FR3D_SERIAL_HOST_DISABLE_GM
        EEPROM_READ_VAR(i, fr3d_serial_filter_msgs);
        fr3d_serial_filter_msgs = true; /* Always ON; not user-visible */
        #endif
        if (fr3d_hall_diameter_enabled > 1)
          fr3d_hall_diameter_enabled = (uint8_t)FR3D_HALL_DIAMETER_ENABLE_DEFAULT;
        if (fr3d_hall_pattern > FR3D_HALL_PATTERN_B)
          fr3d_hall_pattern = (uint8_t)FR3D_HALL_PATTERN_DEFAULT;
        if (fr3d_hall_cal_valid > 1) fr3d_hall_cal_valid = 0;
        if (sinfin_compression_mode > 1)
          sinfin_compression_mode = DEFAULT_SINFIN_COMPRESSION;
        if (fr3d_pred_enabled > 1) fr3d_pred_enabled = (uint8_t)FR3D_PRED_ENABLE_DEFAULT;
        if (fr3d_pred_mode > 1) fr3d_pred_mode = (uint8_t)FR3D_PRED_MODE_DEFAULT;
        fr3d_pred_window_size = (uint8_t)FR3D_PRED_WINDOW_SIZE_DEFAULT;
        if (fr3d_csv_cycle_s != 5 && fr3d_csv_cycle_s != 10)
          fr3d_csv_cycle_s = (uint8_t)FR3D_CSV_CYCLE_S_DEFAULT;
        updatePID();
        eeprom_data_loaded = true;
        SERIAL_ECHO_START;
        SERIAL_ECHOLNPGM("Stored settings retrieved");
    }
    else if (strncmp("V28", stored_ver, 3) == 0)
    {
        eeprom_read_mk3_payload(i);
        EEPROM_READ_VAR(i, fr3d_hall_diameter_enabled);
        EEPROM_READ_VAR(i, fr3d_hall_cal_adc_170);
        EEPROM_READ_VAR(i, fr3d_hall_cal_adc_175);
        EEPROM_READ_VAR(i, fr3d_hall_cal_adc_180);
        EEPROM_READ_VAR(i, fr3d_hall_diam_offset_mm);
        {
          uint8_t fr3d_pred_owner_eeprom_pad = 1;
          EEPROM_READ_VAR(i, fr3d_pred_owner_eeprom_pad);
          (void)fr3d_pred_owner_eeprom_pad;
        }
        EEPROM_READ_VAR(i, fr3d_pred_enabled);
        EEPROM_READ_VAR(i, fr3d_pred_mode);
        EEPROM_READ_VAR(i, fr3d_pred_window_size);
        EEPROM_READ_VAR(i, fr3d_pred_target_diam_mm);
        EEPROM_READ_VAR(i, fr3d_pred_deadband_half_mm);
        EEPROM_READ_VAR(i, fr3d_pred_temp_match_max_c);
        EEPROM_READ_VAR(i, fr3d_pred_r_min);
        EEPROM_READ_VAR(i, fr3d_pred_r_max);
        EEPROM_READ_VAR(i, fr3d_pred_t_min);
        EEPROM_READ_VAR(i, fr3d_pred_t_max);
        EEPROM_READ_VAR(i, fr3d_pred_delta_r_min);
        EEPROM_READ_VAR(i, fr3d_pred_delta_r_max);
        EEPROM_READ_VAR(i, fr3d_pred_k_span_r);
        EEPROM_READ_VAR(i, fr3d_pred_k_err_r);
        EEPROM_READ_VAR(i, fr3d_pred_delta_t_min);
        EEPROM_READ_VAR(i, fr3d_pred_delta_t_max);
        EEPROM_READ_VAR(i, fr3d_pred_k_span_t);
        EEPROM_READ_VAR(i, fr3d_pred_k_err_t);
        EEPROM_READ_VAR(i, fr3d_pred_r_switch_margin);
        EEPROM_READ_VAR(i, fr3d_pred_t_switch_margin);
        EEPROM_READ_VAR(i, fr3d_pred_t_settle_fusions);
        EEPROM_READ_VAR(i, fr3d_diam_jump_debounce_mm);
        EEPROM_READ_VAR(i, fr3d_diam_pending_match_mm);
        EEPROM_READ_VAR(i, fr3d_diam_debug_csv_enabled);
        if (fr3d_diam_jump_debounce_mm < 0.0f) fr3d_diam_jump_debounce_mm = 0.0f;
        else if (fr3d_diam_jump_debounce_mm > 0.5f) fr3d_diam_jump_debounce_mm = 0.5f;
        if (fr3d_diam_pending_match_mm < 0.0f) fr3d_diam_pending_match_mm = 0.0f;
        else if (fr3d_diam_pending_match_mm > 0.2f) fr3d_diam_pending_match_mm = 0.2f;
        if (fr3d_diam_debug_csv_enabled > 1) fr3d_diam_debug_csv_enabled = (uint8_t)FR3D_DIAM_DEBUG_DEFAULT;
        EEPROM_READ_VAR(i, fr3d_csv_cycle_s);
        EEPROM_READ_VAR(i, sinfin_compression_mode);
        #ifdef FR3D_SERIAL_HOST_DISABLE_GM
        EEPROM_READ_VAR(i, fr3d_serial_filter_msgs);
        fr3d_serial_filter_msgs = true; /* Always ON; not user-visible */
        #endif
        if (fr3d_hall_diameter_enabled > 1)
          fr3d_hall_diameter_enabled = (uint8_t)FR3D_HALL_DIAMETER_ENABLE_DEFAULT;
        if (sinfin_compression_mode > 1)
          sinfin_compression_mode = DEFAULT_SINFIN_COMPRESSION;
        if (fr3d_pred_enabled > 1) fr3d_pred_enabled = (uint8_t)FR3D_PRED_ENABLE_DEFAULT;
        if (fr3d_pred_mode > 1) fr3d_pred_mode = (uint8_t)FR3D_PRED_MODE_DEFAULT;
        fr3d_pred_window_size = (uint8_t)FR3D_PRED_WINDOW_SIZE_DEFAULT;
        if (fr3d_csv_cycle_s != 5 && fr3d_csv_cycle_s != 10)
          fr3d_csv_cycle_s = (uint8_t)FR3D_CSV_CYCLE_S_DEFAULT;
        fr3d_hall_migrate_from_legacy_adc();
        updatePID();
        eeprom_data_loaded = true;
        SERIAL_ECHO_START;
        SERIAL_ECHOLNPGM("Stored settings retrieved");
    }
    else if (strncmp("V27", stored_ver, 3) == 0)
    {
        eeprom_read_mk3_payload(i);
        EEPROM_READ_VAR(i, fr3d_hall_diameter_enabled);
        EEPROM_READ_VAR(i, fr3d_hall_cal_adc_170);
        EEPROM_READ_VAR(i, fr3d_hall_cal_adc_175);
        EEPROM_READ_VAR(i, fr3d_hall_cal_adc_180);
        EEPROM_READ_VAR(i, fr3d_hall_diam_offset_mm);
        {
          uint8_t fr3d_pred_owner_eeprom_pad = 1;
          EEPROM_READ_VAR(i, fr3d_pred_owner_eeprom_pad);
          (void)fr3d_pred_owner_eeprom_pad;
        }
        EEPROM_READ_VAR(i, fr3d_pred_enabled);
        EEPROM_READ_VAR(i, fr3d_pred_mode);
        EEPROM_READ_VAR(i, fr3d_pred_window_size);
        EEPROM_READ_VAR(i, fr3d_pred_target_diam_mm);
        EEPROM_READ_VAR(i, fr3d_pred_deadband_half_mm);
        EEPROM_READ_VAR(i, fr3d_pred_temp_match_max_c);
        EEPROM_READ_VAR(i, fr3d_pred_r_min);
        EEPROM_READ_VAR(i, fr3d_pred_r_max);
        EEPROM_READ_VAR(i, fr3d_pred_t_min);
        EEPROM_READ_VAR(i, fr3d_pred_t_max);
        EEPROM_READ_VAR(i, fr3d_pred_delta_r_min);
        EEPROM_READ_VAR(i, fr3d_pred_delta_r_max);
        EEPROM_READ_VAR(i, fr3d_pred_k_span_r);
        EEPROM_READ_VAR(i, fr3d_pred_k_err_r);
        EEPROM_READ_VAR(i, fr3d_pred_delta_t_min);
        EEPROM_READ_VAR(i, fr3d_pred_delta_t_max);
        EEPROM_READ_VAR(i, fr3d_pred_k_span_t);
        EEPROM_READ_VAR(i, fr3d_pred_k_err_t);
        EEPROM_READ_VAR(i, fr3d_pred_r_switch_margin);
        EEPROM_READ_VAR(i, fr3d_pred_t_switch_margin);
        EEPROM_READ_VAR(i, fr3d_pred_t_settle_fusions);
        EEPROM_READ_VAR(i, fr3d_diam_jump_debounce_mm);
        EEPROM_READ_VAR(i, fr3d_diam_pending_match_mm);
        EEPROM_READ_VAR(i, fr3d_diam_debug_csv_enabled);
        if (fr3d_diam_jump_debounce_mm < 0.0f) fr3d_diam_jump_debounce_mm = 0.0f;
        else if (fr3d_diam_jump_debounce_mm > 0.5f) fr3d_diam_jump_debounce_mm = 0.5f;
        if (fr3d_diam_pending_match_mm < 0.0f) fr3d_diam_pending_match_mm = 0.0f;
        else if (fr3d_diam_pending_match_mm > 0.2f) fr3d_diam_pending_match_mm = 0.2f;
        if (fr3d_diam_debug_csv_enabled > 1) fr3d_diam_debug_csv_enabled = (uint8_t)FR3D_DIAM_DEBUG_DEFAULT;
        EEPROM_READ_VAR(i, sinfin_compression_mode);
        #ifdef FR3D_SERIAL_HOST_DISABLE_GM
        EEPROM_READ_VAR(i, fr3d_serial_filter_msgs);
        fr3d_serial_filter_msgs = true; /* Always ON; not user-visible */
        #endif
        if (fr3d_hall_diameter_enabled > 1)
          fr3d_hall_diameter_enabled = (uint8_t)FR3D_HALL_DIAMETER_ENABLE_DEFAULT;
        if (sinfin_compression_mode > 1)
          sinfin_compression_mode = DEFAULT_SINFIN_COMPRESSION;
        if (fr3d_pred_enabled > 1) fr3d_pred_enabled = (uint8_t)FR3D_PRED_ENABLE_DEFAULT;
        if (fr3d_pred_mode > 1) fr3d_pred_mode = (uint8_t)FR3D_PRED_MODE_DEFAULT;
        fr3d_pred_window_size = (uint8_t)FR3D_PRED_WINDOW_SIZE_DEFAULT;
        fr3d_csv_cycle_s = (uint8_t)FR3D_CSV_CYCLE_S_DEFAULT;
        fr3d_hall_migrate_from_legacy_adc();
        updatePID();
        eeprom_data_loaded = true;
        SERIAL_ECHO_START;
        SERIAL_ECHOLNPGM("Stored settings retrieved");
    }
    else if (strncmp("V26", stored_ver, 3) == 0)
    {
        eeprom_read_mk3_payload(i);
        EEPROM_READ_VAR(i, fr3d_hall_diameter_enabled);
        EEPROM_READ_VAR(i, fr3d_hall_cal_adc_170);
        EEPROM_READ_VAR(i, fr3d_hall_cal_adc_175);
        EEPROM_READ_VAR(i, fr3d_hall_cal_adc_180);
        EEPROM_READ_VAR(i, fr3d_hall_diam_offset_mm);
        {
          uint8_t fr3d_pred_owner_eeprom_pad = 1;
          EEPROM_READ_VAR(i, fr3d_pred_owner_eeprom_pad);
          (void)fr3d_pred_owner_eeprom_pad;
        }
        EEPROM_READ_VAR(i, fr3d_pred_enabled);
        EEPROM_READ_VAR(i, fr3d_pred_mode);
        EEPROM_READ_VAR(i, fr3d_pred_window_size);
        EEPROM_READ_VAR(i, fr3d_pred_target_diam_mm);
        EEPROM_READ_VAR(i, fr3d_pred_deadband_half_mm);
        EEPROM_READ_VAR(i, fr3d_pred_temp_match_max_c);
        EEPROM_READ_VAR(i, fr3d_pred_r_min);
        EEPROM_READ_VAR(i, fr3d_pred_r_max);
        EEPROM_READ_VAR(i, fr3d_pred_t_min);
        EEPROM_READ_VAR(i, fr3d_pred_t_max);
        EEPROM_READ_VAR(i, fr3d_pred_delta_r_min);
        EEPROM_READ_VAR(i, fr3d_pred_delta_r_max);
        EEPROM_READ_VAR(i, fr3d_pred_k_span_r);
        EEPROM_READ_VAR(i, fr3d_pred_k_err_r);
        EEPROM_READ_VAR(i, fr3d_pred_delta_t_min);
        EEPROM_READ_VAR(i, fr3d_pred_delta_t_max);
        EEPROM_READ_VAR(i, fr3d_pred_k_span_t);
        EEPROM_READ_VAR(i, fr3d_pred_k_err_t);
        EEPROM_READ_VAR(i, fr3d_pred_r_switch_margin);
        EEPROM_READ_VAR(i, fr3d_pred_t_switch_margin);
        EEPROM_READ_VAR(i, fr3d_pred_t_settle_fusions);
        fr3d_diam_jump_debounce_mm = FR3D_DIAM_JUMP_DEBOUNCE_MM_DEFAULT;
        fr3d_diam_pending_match_mm = FR3D_DIAM_PENDING_MATCH_MM_DEFAULT;
        fr3d_diam_debug_csv_enabled = (uint8_t)FR3D_DIAM_DEBUG_DEFAULT;
        EEPROM_READ_VAR(i, sinfin_compression_mode);
        #ifdef FR3D_SERIAL_HOST_DISABLE_GM
        EEPROM_READ_VAR(i, fr3d_serial_filter_msgs);
        fr3d_serial_filter_msgs = true; /* Always ON; not user-visible */
        #endif
        if (fr3d_hall_diameter_enabled > 1)
          fr3d_hall_diameter_enabled = (uint8_t)FR3D_HALL_DIAMETER_ENABLE_DEFAULT;
        if (sinfin_compression_mode > 1)
          sinfin_compression_mode = DEFAULT_SINFIN_COMPRESSION;
        if (fr3d_pred_enabled > 1) fr3d_pred_enabled = (uint8_t)FR3D_PRED_ENABLE_DEFAULT;
        if (fr3d_pred_mode > 1) fr3d_pred_mode = (uint8_t)FR3D_PRED_MODE_DEFAULT;
        fr3d_pred_window_size = (uint8_t)FR3D_PRED_WINDOW_SIZE_DEFAULT;
        fr3d_csv_cycle_s = (uint8_t)FR3D_CSV_CYCLE_S_DEFAULT;
        fr3d_hall_migrate_from_legacy_adc();
        updatePID();
        eeprom_data_loaded = true;
        SERIAL_ECHO_START;
        SERIAL_ECHOLNPGM("EEPROM V26 -> V27 migrate (DIAMDEBUG)");
        Config_StoreSettings();
        SERIAL_ECHO_START;
        SERIAL_ECHOLNPGM("Stored settings retrieved");
    }
    else if (strncmp("V25", stored_ver, 3) == 0)
    {
        eeprom_read_mk3_payload(i);
        EEPROM_READ_VAR(i, fr3d_hall_diameter_enabled);
        EEPROM_READ_VAR(i, fr3d_hall_cal_adc_170);
        EEPROM_READ_VAR(i, fr3d_hall_cal_adc_175);
        EEPROM_READ_VAR(i, fr3d_hall_cal_adc_180);
        EEPROM_READ_VAR(i, fr3d_hall_diam_offset_mm);
        {
          uint8_t fr3d_pred_owner_eeprom_pad = 1;
          EEPROM_READ_VAR(i, fr3d_pred_owner_eeprom_pad);
          (void)fr3d_pred_owner_eeprom_pad;
        }
        EEPROM_READ_VAR(i, fr3d_pred_enabled);
        EEPROM_READ_VAR(i, fr3d_pred_mode);
        EEPROM_READ_VAR(i, fr3d_pred_window_size);
        EEPROM_READ_VAR(i, fr3d_pred_target_diam_mm);
        EEPROM_READ_VAR(i, fr3d_pred_deadband_half_mm);
        EEPROM_READ_VAR(i, fr3d_pred_temp_match_max_c);
        EEPROM_READ_VAR(i, fr3d_pred_r_min);
        EEPROM_READ_VAR(i, fr3d_pred_r_max);
        EEPROM_READ_VAR(i, fr3d_pred_t_min);
        EEPROM_READ_VAR(i, fr3d_pred_t_max);
        EEPROM_READ_VAR(i, fr3d_pred_delta_r_min);
        EEPROM_READ_VAR(i, fr3d_pred_delta_r_max);
        EEPROM_READ_VAR(i, fr3d_pred_k_span_r);
        EEPROM_READ_VAR(i, fr3d_pred_k_err_r);
        EEPROM_READ_VAR(i, fr3d_pred_delta_t_min);
        EEPROM_READ_VAR(i, fr3d_pred_delta_t_max);
        EEPROM_READ_VAR(i, fr3d_pred_k_span_t);
        EEPROM_READ_VAR(i, fr3d_pred_k_err_t);
        EEPROM_READ_VAR(i, fr3d_pred_r_switch_margin);
        EEPROM_READ_VAR(i, fr3d_pred_t_switch_margin);
        EEPROM_READ_VAR(i, fr3d_pred_t_settle_fusions);
        fr3d_diam_jump_debounce_mm = FR3D_DIAM_JUMP_DEBOUNCE_MM_DEFAULT;
        fr3d_diam_pending_match_mm = FR3D_DIAM_PENDING_MATCH_MM_DEFAULT;
        fr3d_diam_debug_csv_enabled = (uint8_t)FR3D_DIAM_DEBUG_DEFAULT;
        EEPROM_READ_VAR(i, sinfin_compression_mode);
        #ifdef FR3D_SERIAL_HOST_DISABLE_GM
        EEPROM_READ_VAR(i, fr3d_serial_filter_msgs);
        fr3d_serial_filter_msgs = true; /* Always ON; not user-visible */
        #endif
        if (fr3d_hall_diameter_enabled > 1)
          fr3d_hall_diameter_enabled = (uint8_t)FR3D_HALL_DIAMETER_ENABLE_DEFAULT;
        if (sinfin_compression_mode > 1)
          sinfin_compression_mode = DEFAULT_SINFIN_COMPRESSION;
        if (fr3d_pred_enabled > 1) fr3d_pred_enabled = (uint8_t)FR3D_PRED_ENABLE_DEFAULT;
        if (fr3d_pred_mode > 1) fr3d_pred_mode = (uint8_t)FR3D_PRED_MODE_DEFAULT;
        fr3d_pred_window_size = (uint8_t)FR3D_PRED_WINDOW_SIZE_DEFAULT;
        updatePID();
        eeprom_data_loaded = true;
        SERIAL_ECHO_START;
        SERIAL_ECHOLNPGM("EEPROM V25 -> V27 migrate (diam debounce + DIAMDEBUG)");
        Config_StoreSettings();
        SERIAL_ECHO_START;
        SERIAL_ECHOLNPGM("Stored settings retrieved");
    }
    else if (strncmp("V24", stored_ver, 3) == 0)
    {
        eeprom_read_mk3_payload(i);
        EEPROM_READ_VAR(i, fr3d_hall_diameter_enabled);
        EEPROM_READ_VAR(i, fr3d_hall_cal_adc_170);
        EEPROM_READ_VAR(i, fr3d_hall_cal_adc_175);
        EEPROM_READ_VAR(i, fr3d_hall_cal_adc_180);
        EEPROM_READ_VAR(i, fr3d_hall_diam_offset_mm);
        fr3d_pred_enabled = (uint8_t)FR3D_PRED_ENABLE_DEFAULT;
        fr3d_pred_mode = (uint8_t)FR3D_PRED_MODE_DEFAULT;
        fr3d_pred_window_size = (uint8_t)FR3D_PRED_WINDOW_SIZE_DEFAULT;
        fr3d_pred_target_diam_mm = FR3D_PRED_TARGET_DIAM_MM_DEFAULT;
        fr3d_pred_deadband_half_mm = FR3D_PRED_DEADBAND_HALF_MM_DEFAULT;
        fr3d_pred_temp_match_max_c = FR3D_PRED_TEMP_MATCH_MAX_C_DEFAULT;
        fr3d_pred_r_min = FR3D_PRED_R_MIN_DEFAULT;
        fr3d_pred_r_max = FR3D_PRED_R_MAX_DEFAULT;
        fr3d_pred_t_min = (int16_t)FR3D_PRED_T_MIN_DEFAULT;
        fr3d_pred_t_max = (int16_t)FR3D_PRED_T_MAX_DEFAULT;
        fr3d_pred_delta_r_min = FR3D_PRED_DELTA_R_MIN_DEFAULT;
        fr3d_pred_delta_r_max = FR3D_PRED_DELTA_R_MAX_DEFAULT;
        fr3d_pred_k_span_r = FR3D_PRED_K_SPAN_R_DEFAULT;
        fr3d_pred_k_err_r = FR3D_PRED_K_ERR_R_DEFAULT;
        fr3d_pred_delta_t_min = FR3D_PRED_DELTA_T_MIN_DEFAULT;
        fr3d_pred_delta_t_max = (uint8_t)FR3D_PRED_DELTA_T_MAX_DEFAULT;
        fr3d_pred_k_span_t = FR3D_PRED_K_SPAN_T_DEFAULT;
        fr3d_pred_k_err_t = FR3D_PRED_K_ERR_T_DEFAULT;
        fr3d_pred_r_switch_margin = FR3D_PRED_R_SWITCH_MARGIN_DEFAULT;
        fr3d_pred_t_switch_margin = (uint8_t)FR3D_PRED_T_SWITCH_MARGIN_DEFAULT;
        fr3d_pred_t_settle_fusions = (uint8_t)FR3D_PRED_T_SETTLE_FUSIONS_DEFAULT;
        EEPROM_READ_VAR(i, sinfin_compression_mode);
        #ifdef FR3D_SERIAL_HOST_DISABLE_GM
        EEPROM_READ_VAR(i, fr3d_serial_filter_msgs);
        fr3d_serial_filter_msgs = true; /* Always ON; not user-visible */
        #endif
        if (fr3d_hall_diameter_enabled > 1)
          fr3d_hall_diameter_enabled = (uint8_t)FR3D_HALL_DIAMETER_ENABLE_DEFAULT;
        if (sinfin_compression_mode > 1)
          sinfin_compression_mode = DEFAULT_SINFIN_COMPRESSION;
        updatePID();
        eeprom_data_loaded = true;
        SERIAL_ECHO_START;
        SERIAL_ECHOLNPGM("EEPROM V24 -> V25 migrate (predictor params)");
        Config_StoreSettings();
        eeprom_data_loaded = true;
        SERIAL_ECHO_START;
        SERIAL_ECHOLNPGM("Stored settings retrieved");
    }
    else if (strncmp("V23", stored_ver, 3) == 0)
    {
        eeprom_read_mk3_payload(i);
        EEPROM_READ_VAR(i, fr3d_hall_diameter_enabled);
        EEPROM_READ_VAR(i, fr3d_hall_cal_adc_170);
        EEPROM_READ_VAR(i, fr3d_hall_cal_adc_175);
        EEPROM_READ_VAR(i, fr3d_hall_cal_adc_180);
        EEPROM_READ_VAR(i, fr3d_hall_diam_offset_mm);
        {
          uint8_t obsolete_mixer_servos = 0;
          EEPROM_READ_VAR(i, obsolete_mixer_servos);
          (void)obsolete_mixer_servos;
        }
        EEPROM_READ_VAR(i, sinfin_compression_mode);
        #ifdef FR3D_SERIAL_HOST_DISABLE_GM
        EEPROM_READ_VAR(i, fr3d_serial_filter_msgs);
        fr3d_serial_filter_msgs = true; /* Always ON; not user-visible */
        #endif
        if (fr3d_hall_diameter_enabled > 1)
          fr3d_hall_diameter_enabled = (uint8_t)FR3D_HALL_DIAMETER_ENABLE_DEFAULT;
        if (sinfin_compression_mode > 1)
          sinfin_compression_mode = DEFAULT_SINFIN_COMPRESSION;
        updatePID();
        SERIAL_ECHO_START;
        SERIAL_ECHOLNPGM("EEPROM V23 -> V24 migrate (mezclador STM32; byte servos retirado)");
        Config_StoreSettings();
        eeprom_data_loaded = true;
        SERIAL_ECHO_START;
        SERIAL_ECHOLNPGM("Stored settings retrieved");
    }
    else if (strncmp("V22", stored_ver, 3) == 0)
    {
        eeprom_read_mk3_payload(i);
        EEPROM_READ_VAR(i, fr3d_hall_diameter_enabled);
        EEPROM_READ_VAR(i, fr3d_hall_cal_adc_170);
        EEPROM_READ_VAR(i, fr3d_hall_cal_adc_175);
        EEPROM_READ_VAR(i, fr3d_hall_cal_adc_180);
        EEPROM_READ_VAR(i, fr3d_hall_diam_offset_mm);
        EEPROM_READ_VAR(i, sinfin_compression_mode);
        #ifdef FR3D_SERIAL_HOST_DISABLE_GM
        EEPROM_READ_VAR(i, fr3d_serial_filter_msgs);
        fr3d_serial_filter_msgs = true; /* Always ON; not user-visible */
        #endif
        if (fr3d_hall_diameter_enabled > 1)
          fr3d_hall_diameter_enabled = (uint8_t)FR3D_HALL_DIAMETER_ENABLE_DEFAULT;
        if (sinfin_compression_mode > 1)
          sinfin_compression_mode = DEFAULT_SINFIN_COMPRESSION;
        updatePID();
        SERIAL_ECHO_START;
        SERIAL_ECHOLNPGM("EEPROM V22 -> V24 migrate");
        Config_StoreSettings();
        eeprom_data_loaded = true;
        SERIAL_ECHO_START;
        SERIAL_ECHOLNPGM("Stored settings retrieved");
    }
    else if (strncmp("V21", stored_ver, 3) == 0)
    {
        eeprom_read_mk3_payload(i);
        EEPROM_READ_VAR(i, fr3d_hall_diameter_enabled);
        EEPROM_READ_VAR(i, fr3d_hall_cal_adc_170);
        EEPROM_READ_VAR(i, fr3d_hall_cal_adc_175);
        EEPROM_READ_VAR(i, fr3d_hall_cal_adc_180);
        fr3d_hall_diam_offset_mm = FR3D_HALL_DIAM_OFFSET_MM_DEFAULT;
        EEPROM_READ_VAR(i, sinfin_compression_mode);
        #ifdef FR3D_SERIAL_HOST_DISABLE_GM
        EEPROM_READ_VAR(i, fr3d_serial_filter_msgs);
        fr3d_serial_filter_msgs = true; /* Always ON; not user-visible */
        #endif
        if (fr3d_hall_diameter_enabled > 1)
          fr3d_hall_diameter_enabled = (uint8_t)FR3D_HALL_DIAMETER_ENABLE_DEFAULT;
        if (sinfin_compression_mode > 1)
          sinfin_compression_mode = DEFAULT_SINFIN_COMPRESSION;
        updatePID();
        SERIAL_ECHO_START;
        SERIAL_ECHOLNPGM("EEPROM V21 -> V22 migrate");
        Config_StoreSettings();
        eeprom_data_loaded = true;
        SERIAL_ECHO_START;
        SERIAL_ECHOLNPGM("Stored settings retrieved");
    }
    else if (strncmp("V20", stored_ver, 3) == 0)
    {
        eeprom_read_mk3_payload(i);
        fr3d_hall_diameter_enabled = (uint8_t)FR3D_HALL_DIAMETER_ENABLE_DEFAULT;
        fr3d_hall_cal_adc_170 = FR3D_HALL_CAL_ADC_170;
        fr3d_hall_cal_adc_175 = FR3D_HALL_CAL_ADC_175;
        fr3d_hall_cal_adc_180 = FR3D_HALL_CAL_ADC_180;
        EEPROM_READ_VAR(i, sinfin_compression_mode);
        #ifdef FR3D_SERIAL_HOST_DISABLE_GM
        EEPROM_READ_VAR(i, fr3d_serial_filter_msgs);
        fr3d_serial_filter_msgs = true; /* Always ON; not user-visible */
        #endif
        if (sinfin_compression_mode > 1)
          sinfin_compression_mode = DEFAULT_SINFIN_COMPRESSION;
        updatePID();
        SERIAL_ECHO_START;
        SERIAL_ECHOLNPGM("EEPROM V20 -> V21 migrate");
        Config_StoreSettings();
        eeprom_data_loaded = true;
        SERIAL_ECHO_START;
        SERIAL_ECHOLNPGM("Stored settings retrieved");
    }
    else if (strncmp("V19", stored_ver, 3) == 0)
    {
        eeprom_read_mk3_payload(i);
        EEPROM_READ_VAR(i, sinfin_compression_mode);
        #ifdef FR3D_SERIAL_HOST_DISABLE_GM
        EEPROM_READ_VAR(i, fr3d_serial_filter_msgs);
        fr3d_serial_filter_msgs = true; /* Always ON; not user-visible */
        #endif
        if (sinfin_compression_mode > 1)
          sinfin_compression_mode = DEFAULT_SINFIN_COMPRESSION;
        updatePID();
        SERIAL_ECHO_START;
        SERIAL_ECHOLNPGM("EEPROM V19 -> V20 migrate");
        Config_StoreSettings();
        eeprom_data_loaded = true;
        SERIAL_ECHO_START;
        SERIAL_ECHOLNPGM("Stored settings retrieved");
    }
    else if (strncmp("V18", stored_ver, 3) == 0)
    {
        eeprom_read_mk3_payload(i);
        EEPROM_READ_VAR(i, sinfin_compression_mode);
        #ifdef FR3D_SERIAL_HOST_DISABLE_GM
        EEPROM_READ_VAR(i, fr3d_serial_filter_msgs);
        fr3d_serial_filter_msgs = true; /* Always ON; not user-visible */
        #endif
        {
          int hotend0_target_eeprom = 0;
          EEPROM_READ_VAR(i, hotend0_target_eeprom);
#ifndef DELTA
          hotend_standalone_write(hotend0_target_eeprom);
#endif
        }
        if (sinfin_compression_mode > 1)
          sinfin_compression_mode = DEFAULT_SINFIN_COMPRESSION;
        updatePID();
        SERIAL_ECHO_START;
        SERIAL_ECHOLNPGM("EEPROM V18 -> V19 migrate");
        Config_StoreSettings();
        eeprom_data_loaded = true;
        SERIAL_ECHO_START;
        SERIAL_ECHOLNPGM("Stored settings retrieved");
    }
    else if (strncmp("V17", stored_ver, 3) == 0)
    {
        eeprom_read_mk3_payload(i);
        EEPROM_READ_VAR(i, sinfin_compression_mode);
        #ifdef FR3D_SERIAL_HOST_DISABLE_GM
        EEPROM_READ_VAR(i, fr3d_serial_filter_msgs);
        fr3d_serial_filter_msgs = true; /* Always ON; not user-visible */
        #endif
        if (sinfin_compression_mode > 1)
          sinfin_compression_mode = DEFAULT_SINFIN_COMPRESSION;
        updatePID();
        SERIAL_ECHO_START;
        SERIAL_ECHOLNPGM("EEPROM V17 -> V19 migrate");
        Config_StoreSettings();
        eeprom_data_loaded = true;
        SERIAL_ECHO_START;
        SERIAL_ECHOLNPGM("Stored settings retrieved");
    }
    else if (strncmp("V16", stored_ver, 3) == 0)
    {
        eeprom_read_mk3_payload(i);
        EEPROM_READ_VAR(i, sinfin_compression_mode);
        if (sinfin_compression_mode > 1)
          sinfin_compression_mode = DEFAULT_SINFIN_COMPRESSION;
        #ifdef FR3D_SERIAL_HOST_DISABLE_GM
        fr3d_serial_filter_msgs = DEFAULT_FR3D_SERIAL_FILTER_MSGS_ON;
        #endif
        updatePID();
        SERIAL_ECHO_START;
        SERIAL_ECHOLNPGM("EEPROM V16 -> V17 migrate");
        Config_StoreSettings();
        eeprom_data_loaded = true;
        SERIAL_ECHO_START;
        SERIAL_ECHOLNPGM("Stored settings retrieved");
    }
    else if (strncmp("V15", stored_ver, 3) == 0)
    {
        eeprom_read_mk3_payload(i);
        sinfin_compression_mode = DEFAULT_SINFIN_COMPRESSION;
        updatePID();
        SERIAL_ECHO_START;
        SERIAL_ECHOLNPGM("EEPROM V15 -> V16 migrate");
        Config_StoreSettings();
        eeprom_data_loaded = true;
        SERIAL_ECHO_START;
        SERIAL_ECHOLNPGM("Stored settings retrieved");
    }
    else
    {
        Config_ResetDefault();
    }
#endif
#ifndef DELTA
    if (eeprom_data_loaded && apply_standalone_hotend)
      config_apply_standalone_hotend_after_retrieve();
#endif
    #ifdef EEPROM_CHITCHAT
      Config_PrintSettings();
    #endif
}
#endif

void Config_ResetDefault()
{
    float tmp1[]=DEFAULT_AXIS_STEPS_PER_UNIT;
    float tmp2[]=DEFAULT_MAX_FEEDRATE;
    long tmp3[]=DEFAULT_MAX_ACCELERATION;
    for (short i=0;i<5;i++) 
    {
        axis_steps_per_unit[i]=tmp1[i];  
        max_feedrate[i]=tmp2[i];  
        max_acceleration_units_per_sq_second[i]=tmp3[i];
    }
    
    // steps per sq second need to be updated to agree with the units per sq second
    reset_acceleration_rates();
    
    acceleration=DEFAULT_ACCELERATION;
    retract_acceleration=DEFAULT_MOTOR_ACCELERATION;
    minimumfeedrate=DEFAULT_MINIMUMFEEDRATE;
    minsegmenttime=DEFAULT_MINSEGMENTTIME;       
    mintravelfeedrate=DEFAULT_MINTRAVELFEEDRATE;
    max_xy_jerk=DEFAULT_XYJERK;
    max_z_jerk=DEFAULT_ZJERK;
    max_e_jerk=DEFAULT_EJERK;
    add_homeing[0] = add_homeing[1] = add_homeing[2] = 0;
#ifdef DELTA
	endstop_adj[0] = endstop_adj[1] = endstop_adj[2] = 0;
	delta_radius= DELTA_RADIUS;
	delta_diagonal_rod= DELTA_DIAGONAL_ROD;
	delta_segments_per_second= DELTA_SEGMENTS_PER_SECOND;
	recalc_delta_settings(delta_radius, delta_diagonal_rod);
#endif
#ifdef ULTIPANEL
    plaPreheatHotendTemp = PLA_PREHEAT_HOTEND_TEMP;
    plaPreheatHPBTemp = PLA_PREHEAT_HPB_TEMP;
    plaPreheatFanSpeed = PLA_PREHEAT_FAN_SPEED;
    absPreheatHotendTemp = PREHEAT_EXTRUDER_TEMP;
    absPreheatHPBTemp = ABS_PREHEAT_HPB_TEMP;
    default_winder_speed = DEFAULT_WINDER_SPEED;
    
#endif
#ifdef ENABLE_AUTO_BED_LEVELING
    zprobe_zoffset = -Z_PROBE_OFFSET_FROM_EXTRUDER;
#endif
#ifdef DOGLCD
    lcd_contrast = DEFAULT_LCD_CONTRAST;
#endif
#ifdef PIDTEMP
    Kp = DEFAULT_Kp;
    Ki = scalePID_i(DEFAULT_Ki);
    Kd = scalePID_d(DEFAULT_Kd);
    
    // call updatePID (similar to when we have processed M301)
    updatePID();
    
#ifdef PID_ADD_EXTRUSION_RATE
    Kc = DEFAULT_Kc;
#endif//PID_ADD_EXTRUSION_RATE
#endif//PIDTEMP
    
 //load Lyman Extruder defaults   
 extruder_rpm_set= DEFAULT_EXTRUDER_RPM; //setpoint for extruder RPM
 puller_feedrate_default = DEFAULT_PULLER_FEEDRATE; //puller motor feed rate in mm/sec   
 filament_width_desired= DESIRED_FILAMENT_DIA; //holds the desired filament width (i.e like 2.6mm)
 fwidthKp=DEFAULT_fwidthKp;
 fwidthKi=DEFAULT_fwidthKi;  //removed delta T portion since we will handle explicitily
 fwidthKd=DEFAULT_fwidthKd;
 fFactor1=DEFAULT_fFact1;
 fFactor2=DEFAULT_fFact2; 
 pcirc=DEFAULT_PULLER_WHEEL_CIRC;
 sensorRunoutMin = DEFAULT_SENSOR_RUNOUT_MIN;
 sensorRunoutMax = DEFAULT_SENSOR_RUNOUT_MAX;
 fr3d_hall_diameter_enabled = (uint8_t)FR3D_HALL_DIAMETER_ENABLE_DEFAULT;
 fr3d_hall_cal_adc_170 = FR3D_HALL_CAL_ADC_170;
 fr3d_hall_cal_adc_175 = FR3D_HALL_CAL_ADC_175;
 fr3d_hall_cal_adc_180 = FR3D_HALL_CAL_ADC_180;
 fr3d_hall_diam_offset_mm = FR3D_HALL_DIAM_OFFSET_MM_DEFAULT;
 fr3d_hall_pattern = (uint8_t)FR3D_HALL_PATTERN_DEFAULT;
 fr3d_hall_cal_valid = (uint8_t)FR3D_HALL_CAL_VALID_DEFAULT;
 fr3d_hall_cal_mask = 0;
 fr3d_pred_enabled = (uint8_t)FR3D_PRED_ENABLE_DEFAULT;
 fr3d_pred_mode = (uint8_t)FR3D_PRED_MODE_DEFAULT;
 fr3d_pred_window_size = (uint8_t)FR3D_PRED_WINDOW_SIZE_DEFAULT;
 fr3d_pred_target_diam_mm = FR3D_PRED_TARGET_DIAM_MM_DEFAULT;
 fr3d_pred_deadband_half_mm = FR3D_PRED_DEADBAND_HALF_MM_DEFAULT;
 fr3d_pred_temp_match_max_c = FR3D_PRED_TEMP_MATCH_MAX_C_DEFAULT;
 fr3d_pred_r_min = FR3D_PRED_R_MIN_DEFAULT;
 fr3d_pred_r_max = FR3D_PRED_R_MAX_DEFAULT;
 fr3d_pred_t_min = (int16_t)FR3D_PRED_T_MIN_DEFAULT;
 fr3d_pred_t_max = (int16_t)FR3D_PRED_T_MAX_DEFAULT;
 fr3d_pred_delta_r_min = FR3D_PRED_DELTA_R_MIN_DEFAULT;
 fr3d_pred_delta_r_max = FR3D_PRED_DELTA_R_MAX_DEFAULT;
 fr3d_pred_k_span_r = FR3D_PRED_K_SPAN_R_DEFAULT;
 fr3d_pred_k_err_r = FR3D_PRED_K_ERR_R_DEFAULT;
 fr3d_pred_delta_t_min = FR3D_PRED_DELTA_T_MIN_DEFAULT;
 fr3d_pred_delta_t_max = (uint8_t)FR3D_PRED_DELTA_T_MAX_DEFAULT;
 fr3d_pred_k_span_t = FR3D_PRED_K_SPAN_T_DEFAULT;
 fr3d_pred_k_err_t = FR3D_PRED_K_ERR_T_DEFAULT;
 fr3d_pred_r_switch_margin = FR3D_PRED_R_SWITCH_MARGIN_DEFAULT;
 fr3d_pred_t_switch_margin = (uint8_t)FR3D_PRED_T_SWITCH_MARGIN_DEFAULT;
 fr3d_pred_t_settle_fusions = (uint8_t)FR3D_PRED_T_SETTLE_FUSIONS_DEFAULT;
 fr3d_diam_jump_debounce_mm = FR3D_DIAM_JUMP_DEBOUNCE_MM_DEFAULT;
 fr3d_diam_pending_match_mm = FR3D_DIAM_PENDING_MATCH_MM_DEFAULT;
 fr3d_diam_debug_csv_enabled = (uint8_t)FR3D_DIAM_DEBUG_DEFAULT;
 fr3d_csv_cycle_s = (uint8_t)FR3D_CSV_CYCLE_S_DEFAULT;
 sinfin_compression_mode = DEFAULT_SINFIN_COMPRESSION;
#ifdef FR3D_SERIAL_HOST_DISABLE_GM
 fr3d_serial_filter_msgs = DEFAULT_FR3D_SERIAL_FILTER_MSGS_ON;
#endif
 fil_length_cutoff = DEFAULT_LENGTH_CUTOFF;
 
 
SERIAL_ECHO_START;
SERIAL_ECHOLNPGM("Hardcoded Default Settings Loaded");

}
