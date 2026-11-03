#ifndef SWARM_SCENE_H
#define SWARM_SCENE_H
#include <stdint.h>
typedef struct {double x,y,z;} Vec3;
typedef struct {
 unsigned tx,rx,ag,available;double distance,cfo,echo_cfo,delay,echo_delay,gain0,gain1,sigma,phase,echo_phase,spread;
 uint32_t seed;
 double attenuation,loss_db,geometric_doppler;
} LinkConfig;
double scene_time(double communication_seconds);
Vec3 scene_position_physical(unsigned node,double scene_seconds,uint32_t seed);
Vec3 scene_position(unsigned node,double t,uint32_t seed);
void scene_link(unsigned link,double t,uint32_t seed,LinkConfig *c);
uint32_t scene_seed(uint32_t seed,unsigned key,const char *kind);
int scene_configure(const char *hex);
uint32_t scene_config_id(void);
const int32_t *scene_configuration(void);
int scene_node_off(unsigned node,double t);
int scene_external_position(unsigned node,const int32_t xyz_mm[3],double t);
void scene_runtime_reset(void);
int scene_altitude(unsigned node,unsigned altitude_m,double t,uint32_t seed);
unsigned scene_runtime_json(char *out,unsigned capacity);
unsigned scene_terrain_minimum(void);
#endif
