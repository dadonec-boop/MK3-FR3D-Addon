#include "fr3d_gateway_id.h"

#include "MK3.h"
#include <Arduino.h>
#include <ctype.h>
#include <string.h>

char fr3d_gw_id_wifi[FR3D_GW_ID_WIFI_LEN + 1];
char fr3d_gw_id_token[FR3D_GW_ID_TOKEN_LEN + 1];
char fr3d_gw_id_ip[FR3D_GW_ID_IP_LEN + 1];
char fr3d_gw_id_cloud[FR3D_GW_ID_CLOUD_LEN + 1];

static char fr3d_gwid_uc(char c)
{
  if (c >= 'a' && c <= 'z')
    return (char)(c - 'a' + 'A');
  return c;
}

static bool fr3d_gwid_is_token_char(char c)
{
  if (c >= '0' && c <= '9')
    return true;
  if (c >= 'A' && c <= 'Z')
    return true;
  return false;
}

static bool fr3d_gwid_normalize_token(const char *src, char *dst)
{
  if (!src || !dst)
    return false;
  while (*src == ' ' || *src == '\t')
    src++;

  uint8_t n = 0;
  while (*src != '\0' && *src != '\r' && *src != '\n' && *src != ' ' && *src != '\t' && *src != ',') {
    if (n >= FR3D_GW_ID_TOKEN_LEN)
      return false;
    char c = fr3d_gwid_uc(*src++);
    if (!fr3d_gwid_is_token_char(c))
      return false;
    dst[n++] = c;
  }
  dst[n] = '\0';
  return n == FR3D_GW_ID_TOKEN_LEN;
}

static void fr3d_gwid_trim_trailing(char *s)
{
  if (!s)
    return;
  uint8_t n = (uint8_t)strlen(s);
  while (n > 0 && (s[n - 1] == ' ' || s[n - 1] == '\t')) {
    s[n - 1] = '\0';
    n--;
  }
}

static bool fr3d_gwid_copy_wifi_field(const char *src, uint8_t len, char *dst)
{
  if (!src || !dst)
    return false;
  while (len > 0 && (*src == ' ' || *src == '\t')) {
    src++;
    len--;
  }
  while (len > 0 && (src[len - 1] == ' ' || src[len - 1] == '\t'))
    len--;
  if (len == 0 || len > FR3D_GW_ID_WIFI_LEN)
    return false;
  memcpy(dst, src, len);
  dst[len] = '\0';
  return true;
}

bool fr3d_gwid_has_wifi(void)
{
  return fr3d_gw_id_wifi[0] != '\0';
}

bool fr3d_gwid_has_token(void)
{
  return fr3d_gw_id_token[0] != '\0';
}

static bool fr3d_gwid_normalize_cloud(const char *src, char *dst)
{
  if (!src || !dst)
    return false;
  while (*src == ' ' || *src == '\t')
    src++;

  char up[FR3D_GW_ID_CLOUD_LEN + 1];
  uint8_t n = 0;
  while (*src != '\0' && *src != '\r' && *src != '\n' && *src != ' ' && *src != '\t' && *src != ',') {
    if (n >= FR3D_GW_ID_CLOUD_LEN)
      return false;
    up[n++] = fr3d_gwid_uc(*src++);
  }
  up[n] = '\0';
  if (strcmp(up, "ONLINE") == 0 || strcmp(up, "ONL") == 0) {
    strncpy(dst, "ONL", FR3D_GW_ID_CLOUD_LEN + 1);
    return true;
  }
  if (strcmp(up, "OFFLINE") == 0 || strcmp(up, "OFFL") == 0) {
    strncpy(dst, "OFFL", FR3D_GW_ID_CLOUD_LEN + 1);
    return true;
  }
  return false;
}

static bool fr3d_gwid_is_digit(char c)
{
  return c >= '0' && c <= '9';
}

static bool fr3d_gwid_normalize_ip(const char *src, char *dst)
{
  if (!src || !dst)
    return false;
  while (*src == ' ' || *src == '\t')
    src++;

  uint8_t n = 0;
  uint8_t dots = 0;
  while (*src != '\0' && *src != '\r' && *src != '\n' && *src != ' ' && *src != '\t' && *src != ',') {
    if (n >= FR3D_GW_ID_IP_LEN)
      return false;
    if (*src == '.') {
      dots++;
      if (n == 0 || n >= FR3D_GW_ID_IP_LEN - 1)
        return false;
    } else if (!fr3d_gwid_is_digit(*src)) {
      return false;
    }
    dst[n++] = *src++;
  }
  dst[n] = '\0';
  return n >= 7 && dots == 3;
}

bool fr3d_gwid_has_ip(void)
{
  return fr3d_gw_id_ip[0] != '\0';
}

bool fr3d_gwid_has_cloud(void)
{
  return fr3d_gw_id_cloud[0] != '\0';
}

bool fr3d_gwid_cloud_online(void)
{
  return strcmp(fr3d_gw_id_cloud, "ONL") == 0;
}

void fr3d_gwid_clear(void)
{
  fr3d_gw_id_wifi[0] = '\0';
  fr3d_gw_id_token[0] = '\0';
  fr3d_gw_id_ip[0] = '\0';
  fr3d_gw_id_cloud[0] = '\0';
}

void fr3d_gwid_init(void)
{
  fr3d_gwid_clear();
}

static void fr3d_gwid_emit(void)
{
  SERIAL_ECHO_START;
  SERIAL_ECHOLNPGM("ok GWID");
  SERIAL_ECHO_START;
  SERIAL_ECHOPGM("GWID,");
  if (fr3d_gwid_has_wifi()) {
    SERIAL_ECHO(fr3d_gw_id_wifi);
    if (fr3d_gwid_has_token()) {
      SERIAL_ECHOPGM(",");
      SERIAL_ECHO(fr3d_gw_id_token);
    }
    if (fr3d_gwid_has_ip()) {
      SERIAL_ECHOPGM(",");
      SERIAL_ECHO(fr3d_gw_id_ip);
    }
    if (fr3d_gwid_has_cloud()) {
      SERIAL_ECHOPGM(",");
      SERIAL_ECHO(fr3d_gw_id_cloud);
    }
    SERIAL_ECHOLNPGM("");
  } else {
    SERIAL_ECHOLNPGM("");
  }
}

static bool fr3d_gwid_line_prefix(const char *p, const char *word)
{
  for (; *word; ++p, ++word) {
    if (fr3d_gwid_uc(*p) != *word)
      return false;
  }
  return true;
}

bool fr3d_gwid_process_serial(char *p)
{
  while (*p == ' ' || *p == '\t')
    p++;

  if (fr3d_gwid_line_prefix(p, "GWCLR")) {
    char *r = p + 5;
    while (*r == ' ' || *r == '\t')
      r++;
    if (*r != '\0') {
      SERIAL_ECHO_START;
      SERIAL_ECHOLNPGM("err GWCLR");
      return true;
    }
    fr3d_gwid_clear();
    SERIAL_ECHO_START;
    SERIAL_ECHOLNPGM("ok GWCLR");
    return true;
  }

  if (!fr3d_gwid_line_prefix(p, "GWID"))
    return false;

  char *r = p + 4;
  while (*r == ' ' || *r == '\t')
    r++;

  if (*r == '\0' || (r[0] == '?' && (r[1] == '\0' || r[1] == '\r'))) {
    fr3d_gwid_emit();
    return true;
  }

  if (*r == ',') {
    r++;
    while (*r == ' ' || *r == '\t')
      r++;

    char *end = r;
    while (*end != '\0' && *end != '\r' && *end != '\n')
      end++;

    char saved = *end;
    *end = '\0';

    char token[FR3D_GW_ID_TOKEN_LEN + 1];
    char ip[FR3D_GW_ID_IP_LEN + 1];
    char cloud[FR3D_GW_ID_CLOUD_LEN + 1];
    bool has_token = false;
    bool has_ip = false;
    bool has_cloud = false;
    char *last_comma = strrchr(r, ',');
    if (last_comma != NULL && last_comma > r) {
      char *tail_try = last_comma + 1;
      while (*tail_try == ' ' || *tail_try == '\t')
        tail_try++;
      if (fr3d_gwid_normalize_cloud(tail_try, cloud)) {
        has_cloud = true;
        *last_comma = '\0';
        fr3d_gwid_trim_trailing(r);
        last_comma = strrchr(r, ',');
      }
    }
    if (last_comma != NULL && last_comma > r) {
      char *ip_try = last_comma + 1;
      while (*ip_try == ' ' || *ip_try == '\t')
        ip_try++;
      if (fr3d_gwid_normalize_ip(ip_try, ip)) {
        has_ip = true;
        *last_comma = '\0';
        fr3d_gwid_trim_trailing(r);
        last_comma = strrchr(r, ',');
      }
    }
    if (last_comma != NULL && last_comma > r) {
      char *tok_try = last_comma + 1;
      while (*tok_try == ' ' || *tok_try == '\t')
        tok_try++;
      if (fr3d_gwid_normalize_token(tok_try, token)) {
        has_token = true;
        *last_comma = '\0';
        fr3d_gwid_trim_trailing(r);
      }
    }

    uint8_t wifi_len = (uint8_t)strlen(r);
    if (!fr3d_gwid_copy_wifi_field(r, wifi_len, fr3d_gw_id_wifi)) {
      *end = saved;
      SERIAL_ECHO_START;
      SERIAL_ECHOLNPGM("err GWID");
      return true;
    }

    if (has_token) {
      strncpy(fr3d_gw_id_token, token, FR3D_GW_ID_TOKEN_LEN + 1);
    } else {
      fr3d_gw_id_token[0] = '\0';
    }

    if (has_ip) {
      strncpy(fr3d_gw_id_ip, ip, FR3D_GW_ID_IP_LEN + 1);
    } else {
      fr3d_gw_id_ip[0] = '\0';
    }

    if (has_cloud) {
      strncpy(fr3d_gw_id_cloud, cloud, FR3D_GW_ID_CLOUD_LEN + 1);
    } else {
      fr3d_gw_id_cloud[0] = '\0';
    }

    *end = saved;
    SERIAL_ECHO_START;
    SERIAL_ECHOLNPGM("ok GWID SET");
    fr3d_gwid_emit();
    return true;
  }

  SERIAL_ECHO_START;
  SERIAL_ECHOLNPGM("err GWID");
  return true;
}
