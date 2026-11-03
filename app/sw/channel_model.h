#ifndef SWARM_CHANNEL_MODEL_H
#define SWARM_CHANNEL_MODEL_H
#include "scene.h"
#define CHANNEL_FIELDS 48
typedef struct {double gain,phase,cfo,delay,ramp_per_second;unsigned reflections;} ChannelTap;
typedef struct {unsigned count,model,clamped;double fs,loss_db,rain_db_km,scatter_hz;ChannelTap taps[8];double terrain[7];} ChannelFrame;
double channel_digital_scale(const ChannelFrame *frame,double sigma);
void channel_reset(void);
int channel_configure(const char *hex);
const int32_t *channel_configuration(void);
uint32_t channel_config_id(void);
double channel_sample_rate(void);
void channel_frame(unsigned link,double t,uint32_t seed,const LinkConfig *base,ChannelFrame *out);
#endif
