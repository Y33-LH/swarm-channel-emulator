/* Original, camera-independent DEM. Same coordinates as the ARM/reference model. */
((root)=>{
 const height=(x,y,e)=>Math.max(0,[5,5,16,22,10,110,65,85][e]+[8,8,8,8,8,95,48,25][e]*Math.sin(x/680)*Math.cos(y/830)+[2,2,4,7,3,28,12,8][e]*Math.sin((x+y)/340));
 const enabled=c=>c?.channel?.mode===1&&c.channel.reserved0===1;
 const elevation=(x,y,e,t=0)=>{if(e)return height(x,y,e);const blend=start=>{const u=Math.max(0,Math.min(1,(t-start)/20));return u*u*(3-2*u);};const w=blend(300),v=blend(600);return (1-w)*height(x,y,1)+(w-v)*height(x,y,3)+v*height(x,y,4);};
 const ground=(c,e,t=0)=>[5000,5000,enabled(c)?elevation(5000,5000,c.environment??e,t)+10:0];
 const api={height,elevation,enabled,ground,scope:'原创 DEM；可选主障碍刀刃绕射近似；不含建筑、实测地形或真实避障'};
 root.terrainModel=api;if(typeof module!=='undefined')module.exports=api;
})(typeof window==='undefined'?globalThis:window);
