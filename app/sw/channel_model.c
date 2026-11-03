/* ARM creates deterministic model coefficients; FPGA applies the delay,
 * complex products, per-sample amplitude/phase increments and AWGN to samples.
 * Rayleigh/Rician: 32-scatterer SOS, analytically differentiated at frame start.
 * A local amplitude/phase linearization is used within each DATA/ACK frame.
 * Scatter rate is bounded to 5 Hz; tests quantify this approximation separately
 * from receiver performance. Geometric Doppler and oscillator CFO are separate.
 */
#include "channel_model.h"
#include "terrain_model.h"
#include <math.h>
#include <string.h>
#define TAU 6.28318530717958647692
static const int32_t defaults[48]={1,0,0,8000,2,1500,2000,1200,0,0,0,100,300,0,0,0,
 0,0,0,0,-300,125,0,0,-600,250,0,0,-900,375,0,0,-1200,500,0,0,-1500,625,0,0,-1800,750,0,0,-2100,875,0,0};
static int32_t cfg[48]={1,0,0,8000,2,1500,2000,1200,0,0,0,100,300,0,0,0,
 0,0,0,0,-300,125,0,0,-600,250,0,0,-900,375,0,0,-1200,500,0,0,-1500,625,0,0,-1800,750,0,0,-2100,875,0,0};
void channel_reset(void){memcpy(cfg,defaults,sizeof(cfg));}
const int32_t *channel_configuration(void){return cfg;}
double channel_sample_rate(void){return cfg[3]*1000.;}
uint32_t channel_config_id(void){uint32_t h=2166136261U;unsigned i,j;for(i=0;i<48;i++)for(j=0;j<4;j++)h=(h^((cfg[i]>>(j*8))&255))*16777619U;return h;}
static int nib(char c){return c>='0'&&c<='9'?c-'0':c>='a'&&c<='f'?c-'a'+10:-1;}
int channel_configure(const char *hex){
 static const int32_t low[16]={1,0,0,8000,0,0,0,0,-5000,0,0,25,0,0,0,0};
 static const int32_t high[16]={1,2,2,16000,8,3000,5000,6000,5000,35999,60000,400,2400,1,0,0};
 int32_t v[48];unsigned i,j;int a,b;
 if(strlen(hex)!=384)return 1;
 for(i=0;i<48;i++){uint32_t n=0;for(j=0;j<4;j++){a=nib(hex[8*i+2*j]);b=nib(hex[8*i+2*j+1]);if(a<0||b<0)return 1;n|=(uint32_t)(a*16+b)<<(8*j);}v[i]=(int32_t)n;}
 for(i=0;i<16;i++)if(v[i]<low[i]||v[i]>high[i])return 2;
 if((v[3]!=8000&&v[3]!=16000)||(v[1]==0&&v[3]!=8000))return 3;
 if(v[1]==2&&!v[4])return 4;
 for(i=0;i<8;i++){
  j=16+4*i;if(v[j]<-6000||v[j]>0||v[j+1]<0||v[j+1]>60000||v[j+2]<0||v[j+2]>35999||v[j+3]<-5000||v[j+3]>5000)return 2;
  if(v[1]==2&&i<(unsigned)v[4]&&((v[10]+v[j+1])*v[3]/1e6>1023||fabs(v[8]+v[j+3])>6000))return 4;
 }
 if(v[1]==1&&scene_configuration()[2]>=2&&scene_configuration()[2]<=4&&scene_configuration()[13]<1000)return 5;
 if(v[1]==1&&v[13]&&(unsigned)scene_configuration()[5]<scene_terrain_minimum())return 7;
 memcpy(cfg,v,sizeof(cfg));return 0;
}
static double unit(uint32_t seed,unsigned key,const char*name){return (scene_seed(seed,key,name)+.5)/4294967296.;}
/* Common per-frame digital scale preserves signal/noise power ratio and all
 * relative tap coefficients instead of clipping individual Rayleigh peaks.
 * 5 ms covers the maximum scheduled DATA/ACK interval. 4 sigma bounds the
 * quantized Gaussian LUT (actual maximum 3.669 sigma), with rounding margin.
 * The applied scale is reported with the same DATA frame. */
double channel_digital_scale(const ChannelFrame *f,double sigma){
 unsigned i;double peak=0,sum=0,s=1;
 for(i=0;i<f->count;i++){double bound=fmax(0,f->taps[i].gain)+fabs(f->taps[i].ramp_per_second)*.005;peak=fmax(peak,bound);sum+=bound;}
 if(peak>.98)s=.98/peak;
 if(8192*sum+4*sigma>30000)s=fmin(s,30000/(8192*sum+4*sigma));
 return s;
}
/* ITU-R P.838-3, equations (2),(3), vertical polarization tables 2 and 4.
 * Valid 1..1000 GHz; this product enables rain scenarios only at 1..6 GHz.
 */
static double rain(double ghz,double rate){
 static const double ak[4]={-3.80595,-3.44965,-.39902,.50167},bk[4]={.56934,-.22911,.73042,1.07319},ck[4]={.81061,.51059,.11899,.27195};
 static const double aa[5]={-.07771,.56727,-.20238,-48.2991,48.5833},ba[5]={2.33840,.95545,1.14520,.791669,.791459},ca[5]={-.76284,.54039,.26809,.116226,.116479};
 double x,k,a,z;unsigned i;if(rate<=0||ghz<1)return 0;x=log10(ghz);k=-.16398*x+.63297;a=-.053739*x+.83433;
 for(i=0;i<4;i++){z=(x-bk[i])/ck[i];k+=ak[i]*exp(-z*z);}
 for(i=0;i<5;i++){z=(x-ba[i])/ca[i];a+=aa[i]*exp(-z*z);}
 return pow(10,k)*pow(rate,a);
}
static void scatter(unsigned link,unsigned tap,double t,uint32_t seed,double fd,unsigned model,double kfactor,double *amp,double *phase,double *slope,double *freq){
 double re=0,im=0,dr=0,di=0,angle,w,p,co,si,norm,power;unsigned m,key;
 if(!model){*amp=1;*phase=0;*slope=0;*freq=0;return;}
 for(m=0;m<32;m++){
  key=link*256+tap*32+m;angle=TAU*(m+unit(seed,key,"angle"))/32;
  w=TAU*fd*cos(angle);p=w*t+TAU*unit(seed,key,"scatter");co=cos(p);si=sin(p);
  re+=co;im+=si;dr-=w*si;di+=w*co;
 }
 norm=1/sqrt(32.);re*=norm;im*=norm;dr*=norm;di*=norm;
 if(model==2){norm=1/sqrt(1+kfactor);re=re*norm+sqrt(kfactor/(1+kfactor));im*=norm;dr*=norm;di*=norm;}
 power=re*re+im*im;*amp=sqrt(power);*phase=atan2(im,re);
 *slope=power>1e-12?(re*dr+im*di)/sqrt(power):0;
 *freq=power>1e-12?(re*di-im*dr)/(TAU*power):0;
}
void channel_frame(unsigned link,double t,uint32_t seed,const LinkConfig *base,ChannelFrame *o){
 t=scene_time(t);
 const int32_t *s=scene_configuration();unsigned i,n=(unsigned)cfg[4],env=s[1]?s[1]:(t<300?1:t<600?3:4),ag=base->ag;
 static const double tau_ns[8]={0,125,187.5,250,500,1000,500,250},echo_db[8]={0,-18,-15,-12,-9,-10,-13,-16};
 static const double old_weather[8]={0,.01,.02,.05,.15,.01,.03,.08};
 double weights[8],sum=0,amp,ph,slope,freq,scale,g,ed=0,p0=0,delay=0,rate=0,fd=cfg[6]/1000.,K=pow(10,cfg[5]/1000.);
 if(!n){static const unsigned counts[8]={2,2,3,4,6,7,5,3};n=counts[env]+ag+(s[5]<200?1:0);if(s[5]>=650&&n>1)n--;if(n>8)n=8;}
 memset(o,0,sizeof(*o));o->fs=channel_sample_rate();o->count=n;o->model=cfg[2];o->scatter_hz=fd;
 if(!cfg[1]){
  o->count=2;o->loss_db=base->loss_db;
  o->taps[0].gain=base->gain0;o->taps[0].phase=base->phase;o->taps[0].cfo=base->cfo;o->taps[0].delay=base->delay;
  o->taps[1].gain=base->gain1;o->taps[1].phase=base->echo_phase;o->taps[1].cfo=base->echo_cfo;o->taps[1].delay=base->delay+base->echo_delay;return;
 }
 if(cfg[1]==1){
  if(s[2]>=2&&s[2]<=4)rate=s[2]==2?2:s[2]==3?10:50;
  o->rain_db_km=rain(s[13]/1000.,rate);
  o->loss_db=base->loss_db-old_weather[s[2]]*base->distance/1000*(ag?1.5:1)+o->rain_db_km*base->distance/1000;
  // Fog/snow: keep explicit small empirical surface-loss assumptions separate
  // from the standardized rain term. No unsupported "3GPP terrain" claim.
  if(s[2]==1||s[2]>=5)o->loss_db+=(s[2]==1?.003:.02*(s[2]-4))*base->distance/1000;
  if(cfg[13]){
   Vec3 p=scene_position_physical(base->tx,t,seed),q=scene_position_physical(base->rx,t,seed);
   TerrainPath r=terrain_path(p.x,p.y,p.z,q.x,q.y,q.z,s[1],t,s[13]*1e6);
   o->terrain[0]=r.loss_db;o->terrain[1]=r.nu;o->terrain[2]=r.clearance_m;
   o->terrain[3]=r.x;o->terrain[4]=r.y;o->terrain[5]=r.height_m;o->terrain[6]=r.ground_z;
   o->loss_db+=r.loss_db;
  }
  g=pow(10,-o->loss_db/20);ed=base->echo_cfo-base->cfo;p0=base->phase;delay=base->distance/299792458.*o->fs;
  for(i=0;i<n;i++){weights[i]=i?pow(10,(echo_db[env]+(ag?3:0)-6-(i-1)*cfg[12]/100.)/10):1;sum+=weights[i];}
 }else{
  o->loss_db=cfg[7]/100.;g=pow(10,-o->loss_db/20);p0=cfg[9]*TAU/36000.;delay=cfg[10]*o->fs/1e9;
  for(i=0;i<n;i++){weights[i]=pow(10,cfg[16+4*i]/1000.);sum+=weights[i];}
 }
 for(i=0;i<n;i++){
  ChannelTap *a=&o->taps[i];scale=g*sqrt(weights[i]/sum);
  scatter(link,i,t,seed,fd,cfg[2],K,&amp,&ph,&slope,&freq);
  a->gain=scale*amp;a->ramp_per_second=scale*slope;
  a->phase=p0+ph+(cfg[1]==2?cfg[18+4*i]*TAU/36000.:(i?TAU*unit(seed,link*8+i,"tap_phase")+TAU*i*ed*t:0));
  a->cfo=(cfg[1]==2?cfg[8]+cfg[19+4*i]:base->cfo+i*ed)+freq;
  a->delay=delay+(cfg[1]==2?cfg[17+4*i]*o->fs/1e9:i*tau_ns[env]*(ag?2:1)*cfg[11]/100.*o->fs/1e9);
  a->reflections=i?1+(i-1)/2:0; // equivalent profile order, not traced geometric rays
  if(a->delay>1023||fabs(a->cfo)>100000)o->clamped++;
 }
}
