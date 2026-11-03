/* Procedural DEM shared with reference/terrain_model.py and ui/terrain-model.js.
 * One dominant sampled knife edge, ITU-R P.526-16 equations 26/31.
 * This is an educational approximation, NOT ray tracing, measured terrain,
 * building penetration, or a full multiple-obstacle P.526 implementation.
 * Coordinates and elevations are metres in the same flat local datum.
 */
#ifndef SWARM_TERRAIN_MODEL_H
#define SWARM_TERRAIN_MODEL_H
#include <math.h>
typedef struct {double loss_db,nu,clearance_m,x,y,height_m,ground_z;} TerrainPath;
static double terrain_height(double x,double y,unsigned env){
 static const double base[8]={5,5,16,22,10,110,65,85};
 static const double amp[8]={8,8,8,8,8,95,48,25};
 static const double secondary[8]={2,2,4,7,3,28,12,8};
 if(env>7)env=1;
 return fmax(0,base[env]+amp[env]*sin(x/680.)*cos(y/830.)+secondary[env]*sin((x+y)/340.));
}
static double terrain_edge_loss(double nu){double v=nu-.1;return nu<=-.78?0:fmax(0,6.9+20*log10(sqrt(v*v+1)+v));}
static double terrain_blend(double t,double start){double u=fmax(0,fmin(1,(t-start)/20));return u*u*(3-2*u);}
static double terrain_elevation(double x,double y,unsigned env,double t){
 double w,v;if(env)return terrain_height(x,y,env);w=terrain_blend(t,300);v=terrain_blend(t,600);
 return (1-w)*terrain_height(x,y,1)+(w-v)*terrain_height(x,y,3)+v*terrain_height(x,y,4);
}
static TerrainPath terrain_path(double px,double py,double pz,double qx,double qy,double qz,unsigned env,double t,double fc){
 TerrainPath o={0,-1e9,1e9,0,0,0,0};unsigned i;
 double horizontal=hypot(qx-px,qy-py),distance=hypot(horizontal,qz-pz),lambda=299792458./fc;
 o.ground_z=terrain_elevation(5000,5000,env,t)+10;
 if(horizontal<1||distance<1||fc<=0)return o;
 for(i=1;i<64;i++){
  double u=i/64.,x=px+(qx-px)*u,y=py+(qy-py)*u,z=terrain_elevation(x,y,env,t);
  double clearance=pz+(qz-pz)*u-z,h=-clearance*horizontal/distance;
  double nu=h*sqrt(2/(lambda*distance*u*(1-u)));
  if(nu>o.nu){o.nu=nu;o.clearance_m=clearance;o.x=x;o.y=y;o.height_m=z;}
 }
 o.loss_db=terrain_edge_loss(o.nu);return o;
}
#endif
