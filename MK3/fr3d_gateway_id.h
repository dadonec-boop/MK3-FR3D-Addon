#ifndef FR3D_GATEWAY_ID_H
#define FR3D_GATEWAY_ID_H

#include <stdint.h>

#define FR3D_GW_ID_WIFI_LEN 40
#define FR3D_GW_ID_TOKEN_LEN 8
#define FR3D_GW_ID_IP_LEN 15
#define FR3D_GW_ID_CLOUD_LEN 7

extern char fr3d_gw_id_wifi[FR3D_GW_ID_WIFI_LEN + 1];
extern char fr3d_gw_id_token[FR3D_GW_ID_TOKEN_LEN + 1];
extern char fr3d_gw_id_ip[FR3D_GW_ID_IP_LEN + 1];
extern char fr3d_gw_id_cloud[FR3D_GW_ID_CLOUD_LEN + 1];

void fr3d_gwid_init(void);
void fr3d_gwid_clear(void);
bool fr3d_gwid_has_wifi(void);
bool fr3d_gwid_has_token(void);
bool fr3d_gwid_has_ip(void);
bool fr3d_gwid_has_cloud(void);
bool fr3d_gwid_cloud_online(void);
bool fr3d_gwid_process_serial(char *p);

#endif
