#include "scene.h"
#include <math.h>
#include <stdio.h>
#include <string.h>
#define PI 3.14159265358979323846
#define TAU (2*PI)
static const int bx[16]={1000,2000,3000,4000,1000,2000,3000,4000,9000,8000,7000,6000,9000,8000,7000,6000};
static const int by[16]={1000,2000,3000,4000,9000,8000,7000,6000,9000,8000,7000,6000,1000,2000,3000,4000};
static const int osc[17]={0,-113,24,161,-203,-66,71,208,-156,-19,118,-246,-109,28,165,-199,-62};
static uint32_t seed_uncached(uint32_t seed,unsigned key,const char *kind){char b[80];unsigned i,j;uint32_t c=~0U;snprintf(b,sizeof(b),"A2|%u|%u|%s",(unsigned)seed,key,kind);for(i=0;b[i];i++){c^=(unsigned char)b[i];for(j=0;j<8;j++)c=(c>>1)^(0xedb88320U&-(c&1));}c=~c;return c?c:1;}
typedef struct {uint32_t seed,key,value;char kind[16];} SeedCache;
static SeedCache seed_cache[512];
uint32_t scene_seed(uint32_t seed,unsigned key,const char *kind){
 unsigned h=(seed*31U+key*19U+(unsigned char)kind[0]*7U+(unsigned char)kind[strlen(kind)-1])%512;
 SeedCache *c=&seed_cache[h];if(c->value&&c->seed==seed&&c->key==key&&!strcmp(c->kind,kind))return c->value;
 c->seed=seed;c->key=key;c->value=seed_uncached(seed,key,kind);snprintf(c->kind,sizeof(c->kind),"%s",kind);return c->value;
}
static double phase(uint32_t seed,unsigned n,const char *kind){return scene_seed(seed,n,kind)*(TAU/4294967296.0);}
static double smooth(double t,double start,double length){double u=(t-start)/length;if(u<0)u=0;if(u>1)u=1;return u*u*(3-2*u);}
static double blend(double t,double a,double b,double c){double w=smooth(t,300,20),v=smooth(t,600,20);return (1-w)*a+(w-v)*b+v*c;}
static double fluct(double t,uint32_t seed,unsigned k,double period){return .6*sin(TAU*t/period+phase(seed,k,"slow1"))+.4*sin(TAU*t/(period*1.73)+phase(seed,k,"slow2"));}
Vec3 legacy_position(unsigned node,double t,uint32_t seed){Vec3 v;double p,np,a;if(!node){v.x=5000;v.y=5000;v.z=0;return v;}p=((node-1)/4)*PI/2;np=(node-1)*TAU/16;a=blend(t,3,9,18);
 v.x=bx[node-1]+400*(cos(TAU*t/180+p)-cos(p))+40*(sin(TAU*t/120+np)-sin(np))+a*fluct(t,seed,node*3,37);
 v.y=by[node-1]+400*(sin(TAU*t/180+p)-sin(p))+a*fluct(t,seed,node*3+1,41);
 v.z=400+30*(sin(TAU*t/120+np)-sin(np))+.3*a*fluct(t,seed,node*3+2,43);return v;
}
static Vec3 velocity(unsigned node,double t,uint32_t seed){Vec3 a=legacy_position(node,t-.001,seed),b=legacy_position(node,t+.001,seed),v;v.x=(b.x-a.x)/.002;v.y=(b.y-a.y)/.002;v.z=(b.z-a.z)/.002;return v;}
void legacy_link(unsigned link,double t,uint32_t seed,LinkConfig *c){
 unsigned base=link%16,tx=base+1,rx=(tx%4)?tx+1:0,ag=(rx==0),tmp;Vec3 p,q,vp,vq;double dx,dy,dz,radial,eta,extra,echo_db,depth,period,noise,ed,spread,loss_jitter,noise_jitter,fault,loss,g,r,q0,f0,f1;
 if(link>=16){tmp=tx;tx=rx;rx=tmp;}c->tx=tx;c->rx=rx;c->ag=ag;
 p=legacy_position(tx,t,seed);q=legacy_position(rx,t,seed);vp=velocity(tx,t,seed);vq=velocity(rx,t,seed);dx=q.x-p.x;dy=q.y-p.y;dz=q.z-p.z;
 c->distance=sqrt(dx*dx+dy*dy+dz*dz);radial=((vq.x-vp.x)*dx+(vq.y-vp.y)*dy+(vq.z-vp.z)*dz)/c->distance;
 eta=ag?blend(t,2.2,2.6,3):blend(t,2,2.2,2.4);extra=ag?blend(t,0,4,6):blend(t,0,2,4);echo_db=ag?blend(t,-15,-10,-6):blend(t,-18,-12,-9);
 c->echo_delay=8*(ag?blend(t,.25,.5,1):blend(t,.125,.25,.5));depth=ag?blend(t,.1,.2,.35):blend(t,.05,.1,.2);period=ag?blend(t,6,4,3):blend(t,8,6,4);
 noise=ag?blend(t,1,3,5):blend(t,0,1,2);ed=(ag?blend(t,2,4,8):blend(t,1,2,5))*((scene_seed(seed,link,"echo_sign")&1)?1:-1);
 spread=blend(t,.2,.6,1.2)*(ag?1.5:1);c->spread=spread;loss_jitter=spread*fluct(t,seed,1000+link,17);noise_jitter=.5*spread*fluct(t,seed,2000+link,19);
 fault=(t>=660&&t<700&&(tx==12||rx==12))?smooth(t,660,1)*(1-smooth(t,699,1)):0;
 loss=10*eta*log10((c->distance>1000?c->distance:1000)/1000)+extra+loss_jitter+12*fault;
 // Explicit uncoded_baseline_v2 overlay; see reference/baseline_profile.json.
 g=pow(10,-loss/20);r=pow(10,(echo_db-6)/20);q0=1/sqrt(1+r*r);
 f0=1-depth*(1-cos(TAU*t/period+phase(seed,link,"fade0")))/2;f1=1-depth*(1-cos(TAU*t/(period*.8)+phase(seed,link,"fade1")))/2;
 c->gain0=g*q0*f0;c->gain1=g*r*q0*f1;c->sigma=sqrt((8192.0*8192)/(2*pow(10,3.4)))*pow(10,(noise+noise_jitter+6*fault)/20);
 c->delay=c->distance/299792458.0*8000000.;c->cfo=osc[tx]-osc[rx]-2400000000.*radial/299792458.0;c->echo_cfo=c->cfo+ed;
 c->phase=fmod(-TAU*2400000000.*c->distance/299792458.0+TAU*(osc[tx]-osc[rx])*t,TAU);if(c->phase<0)c->phase+=TAU;
 c->echo_phase=fmod(c->phase+phase(seed,link,"echo")+TAU*ed*t,TAU);if(c->echo_phase<0)c->echo_phase+=TAU;
 c->seed=scene_seed(seed,link,"fast");c->available=!(t>=330&&t<370&&(tx==2||rx==2));
}
