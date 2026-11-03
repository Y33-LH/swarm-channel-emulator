/* Controlled, bounded scene profiles. No packet outcomes are decided here.
 * TX coordinates -> physical link parameters -> PL registers -> RX results.
 * Weather effects are experiment assumptions, not certified meteorological models. */
#include "scene.h"
#include "formation_points.h"
#include <math.h>
#include <string.h>
#define TAU 6.28318530717958647692
extern Vec3 legacy_position(unsigned,double,uint32_t);
extern void legacy_link(unsigned,double,uint32_t,LinkConfig*);
static int32_t cfg[16]={1,0,0,0,300,400,5000,5000,12000,0,3400,1,100,2400,0,0};
static unsigned external_valid;
static Vec3 external_position;
static unsigned altitude_valid[17];
static double altitude_from[17],altitude_to[17],altitude_at[17];
void scene_runtime_reset(void){external_valid=0;memset(altitude_valid,0,sizeof(altitude_valid));}
int scene_external_position(unsigned node,const int32_t xyz[3]){if(!node||node!=(unsigned)cfg[14]||xyz[0]<0||xyz[0]>10000000||xyz[1]<0||xyz[1]>10000000||xyz[2]<50000||xyz[2]>900000)return 0;external_position.x=xyz[0]/1000.;external_position.y=xyz[1]/1000.;external_position.z=xyz[2]/1000.;external_valid=1;return 1;}
static const int osc[17]={0,-113,24,161,-203,-66,71,208,-156,-19,118,-246,-109,28,165,-199,-62};
static const int low[16]={1,0,0,0,150,100,500,500,0,0,1800,0,0,200,0,0};
static const int high[16]={1,7,7,8,1100,800,9500,9500,20000,359,4500,1,200,6000,16,0};
const int32_t *scene_configuration(void){return cfg;}
uint32_t scene_config_id(void){uint32_t h=2166136261U;unsigned i,j;for(i=0;i<16;i++)for(j=0;j<4;j++)h=(h^((cfg[i]>>(j*8))&255))*16777619U;return h;}
static int nib(char c){return c>='0'&&c<='9'?c-'0':c>='a'&&c<='f'?c-'a'+10:-1;}
int scene_configure(const char *hex){int32_t temp[16];unsigned i,j;double radius=0,available;int a,b;
 if(strlen(hex)!=128)return 1;
 for(i=0;i<16;i++){uint32_t n=0;for(j=0;j<4;j++){a=nib(hex[i*8+j*2]);b=nib(hex[i*8+j*2+1]);if(a<0||b<0)return 1;n|=(uint32_t)(a*16+b)<<(j*8);}temp[i]=(int32_t)n;if(temp[i]<low[i]||temp[i]>high[i])return 2;}
 if(temp[14]==9||temp[14]==13)return 5;
 if(temp[3]){for(i=0;i<16;i++){double r=hypot(formation_xy[temp[3]][i][0],formation_xy[temp[3]][i][1]);if(r>radius)radius=r;}radius=radius*temp[4]+400;available=fmin(fmin(temp[6],10000-temp[6]),fmin(temp[7],10000-temp[7]));if(radius>available)return 3;}
 else if(temp[4]!=300||temp[5]!=400||temp[6]!=5000||temp[7]!=5000||temp[8]!=12000||temp[9])return 3;
 memcpy(cfg,temp,sizeof(cfg));scene_runtime_reset();return 0;
}
static double phase(uint32_t seed,unsigned n,const char *kind){return scene_seed(seed,n,kind)*(TAU/4294967296.0);}
static double fluct(double t,uint32_t s,unsigned k,double p){return .6*sin(TAU*t/p+phase(s,k,"slow1"))+.4*sin(TAU*t/(p*1.73)+phase(s,k,"slow2"));}
static double smooth(double t,double start,double length){double u=(t-start)/length;if(u<0)u=0;if(u>1)u=1;return u*u*(3-2*u);}
static double blend(double t,double a,double b,double c){double w=smooth(t,300,20),v=smooth(t,600,20);return (1-w)*a+(w-v)*b+v*c;}
/* Each row: AA loss exponent, excess dB, echo dB, delay us, fade, period s,
 * noise excess dB, echo Doppler Hz, loss fluctuation bound dB, position jitter m.
 * AG adds its explicitly stronger and less stable overlay below. */
static const double environments[8][10]={
 {0}, {2,0,-18,.125,.05,8,0,1,.2,3},
 {2.1,1,-15,.1875,.075,7,.5,1.5,.4,6},
 {2.2,2,-12,.25,.1,6,1,2,.6,9},
 {2.4,4,-9,.5,.2,4,2,5,1.2,18},
 {2.3,3,-10,1,.18,5,1.5,4,1,12},
 {2.2,2,-13,.5,.12,6,1,3,.7,9},
 {2.05,.5,-16,.25,.08,7,.4,2,.35,5}};
static const double weather_loss[8]={0,.01,.02,.05,.15,.01,.03,.08};
static const double weather_motion[8]={0,.1,.2,.4,.8,.2,.4,.7};
static double parameter(unsigned k,double t){if(cfg[1])return environments[cfg[1]][k];return blend(t,environments[1][k],environments[3][k],environments[4][k]);}
int scene_node_off(unsigned node,double t){return cfg[11]&&node==2&&t>=330&&t<370;}
Vec3 scene_position(unsigned node,double t,uint32_t seed){Vec3 v;double a,theta,x,y,j,fr,av,orbit;unsigned i2;
 if(node==0){v.x=5000;v.y=5000;v.z=0;return v;}
 if(node>16){v.x=v.y=v.z=0;return v;}
 if(external_valid&&node==(unsigned)cfg[14])return external_position;
 if(!cfg[3]){v=legacy_position(node,t,seed);if(altitude_valid[node])v.z=altitude_from[node]+(altitude_to[node]-altitude_from[node])*smooth(t,altitude_at[node],10);return v;}
 /* 蜂群整体绕场景中心公转：轨道半径取"可用区域的80%减去编队自身半径"，
  * 使编队可达范围覆盖地图约80%宽度；角速度由线速度/轨道半径得出，
  * 线速度不变则多普勒特性与旧版一致。编队内部相对位置不变。 */
 fr=0;for(i2=0;i2<16;i2++){double r=hypot(formation_xy[cfg[3]][i2][0],formation_xy[cfg[3]][i2][1]);if(r>fr)fr=r;}
 fr=fr*cfg[4]+400;
 av=fmin(fmin(cfg[6],10000-cfg[6]),fmin(cfg[7],10000-cfg[7]));
 orbit=cfg[8]?fmax(0,.9*av-fr):0;
 theta=cfg[8]&&orbit>1?cfg[8]/1000./orbit*t:0;
 a=cfg[9]*TAU/360;
 x=formation_xy[cfg[3]][node-1][0]*cfg[4];y=formation_xy[cfg[3]][node-1][1]*cfg[4];
 j=fmin(.08*cfg[4],parameter(9,t)*cfg[12]/100.*(1+weather_motion[cfg[2]]));
 v.x=cfg[6]+x*cos(a)-y*sin(a)+orbit*sin(theta)+j*fluct(t,seed,node*3,37);
 v.y=cfg[7]+x*sin(a)+y*cos(a)+orbit*cos(theta)+j*fluct(t,seed,node*3+1,41);
 v.z=cfg[5]+.3*j*fluct(t,seed,node*3+2,43);if(altitude_valid[node])v.z=altitude_from[node]+(altitude_to[node]-altitude_from[node])*smooth(t,altitude_at[node],10);return v;
}
int scene_altitude(unsigned node,unsigned altitude_m,double t,uint32_t seed){Vec3 old;if(node<1||node>16||altitude_m<100||altitude_m>800||node==(unsigned)cfg[14])return 0;old=scene_position(node,t,seed);if(fabs(altitude_m-old.z)>100)return 0;altitude_from[node]=old.z;altitude_to[node]=altitude_m;altitude_at[node]=t;altitude_valid[node]=1;return 1;}
static Vec3 velocity(unsigned n,double t,uint32_t s){Vec3 a=scene_position(n,t-.001,s),b=scene_position(n,t+.001,s),v;v.x=(b.x-a.x)/.002;v.y=(b.y-a.y)/.002;v.z=(b.z-a.z)/.002;return v;}
void scene_link(unsigned link,double t,uint32_t seed,LinkConfig*c){
 unsigned tx=link%16+1,rx=tx%4?tx+1:0,ag=(rx==0),tmp;Vec3 p,q,vp,vq;double dx,dy,dz,radial,eta,extra,echo,depth,period,noise,ed,loss,g,r,q0,fault,fc;
 /* Protocol 20 always uses this model: no hidden legacy branch may ignore fc.
  * Historical protocol <=18 records retain their original Python reference. */
 if(link>=16){tmp=tx;tx=rx;rx=tmp;}c->tx=tx;c->rx=rx;c->ag=ag;
 p=scene_position(tx,t,seed);q=scene_position(rx,t,seed);vp=velocity(tx,t,seed);vq=velocity(rx,t,seed);dx=q.x-p.x;dy=q.y-p.y;dz=q.z-p.z;
 c->distance=sqrt(dx*dx+dy*dy+dz*dz);radial=((vq.x-vp.x)*dx+(vq.y-vp.y)*dy+(vq.z-vp.z)*dz)/fmax(1,c->distance);
 eta=parameter(0,t)+(ag?.2:0);extra=parameter(1,t)+(ag?2:0);echo=parameter(2,t)+(ag?3:0);
 depth=parameter(4,t)*(ag?1.5:1);period=parameter(5,t)*(ag?.75:1);noise=parameter(6,t)+(ag?2:0);
 c->spread=parameter(8,t)*(ag?1.5:1)*cfg[12]/100.;
 fault=cfg[11]&&t>=660&&t<700&&(tx==12||rx==12)?smooth(t,660,1)*(1-smooth(t,699,1)):0;
 /* Bounded normalized path-loss law, d0=1 km. Strictly monotone below d0,
  * asymptotic exponent eta above d0; no absolute RF link-budget claim. */
 loss=10*eta*log10(1+c->distance/1000)+extra+c->spread*fluct(t,seed,1000+link,17)+12*fault+weather_loss[cfg[2]]*c->distance/1000*(ag?1.5:1);
 g=pow(10,-loss/20);r=pow(10,(echo-6)/20);q0=1/sqrt(1+r*r);
 c->gain0=g*q0*(1-depth*(1-cos(TAU*t/period+phase(seed,link,"fade0")))/2);
 c->gain1=g*r*q0*(1-depth*(1-cos(TAU*t/(period*.8)+phase(seed,link,"fade1")))/2);
 /* AWGN referenced to unit transmit sample power; only user SNR controls it.
  * Path attenuation/fading may change received SNR, never the noise setting. */
 c->sigma=sqrt(8192.*8192/(2*pow(10,cfg[10]/1000.)));
 c->delay=c->distance/299792458.*8000000.;c->echo_delay=parameter(3,t)*8*(ag?2:1);
 fc=cfg[13]*1000000.;c->cfo=osc[tx]-osc[rx]-fc*radial/299792458.;ed=parameter(7,t)*(ag?1.6:1)*((scene_seed(seed,link,"echo_sign")&1)?1:-1);c->echo_cfo=c->cfo+ed;
 c->phase=fmod(-TAU*fc*c->distance/299792458.+TAU*(osc[tx]-osc[rx])*t,TAU);if(c->phase<0)c->phase+=TAU;
 c->echo_phase=fmod(c->phase+phase(seed,link,"echo")+TAU*ed*t,TAU);if(c->echo_phase<0)c->echo_phase+=TAU;
 c->seed=scene_seed(seed,link,"fast");c->available=!(scene_node_off(tx,t)||scene_node_off(rx,t));
}
