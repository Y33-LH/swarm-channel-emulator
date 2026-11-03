/* Included by network.c after common frame helpers. This is a scheduler/driver,
 * not a business proxy: never constructs a hardware node's frame or ACK. */
static unsigned hw_last[2][5],hw_altitude_seen[2],hw_enabled[2]={1,1};
static unsigned hw_base(unsigned n){return n==9?0x400:n==13?0x800:0;}
static unsigned hw_source(unsigned n){return n==9?1:n==13?2:0;}
static int hw_wait(unsigned node){unsigned b=hw_base(node),guard=10000;while((rd(b+0x40)&1)&&--guard){}if(!guard||rd(b+0x88)){running=0;fatal_code=200+rd(b+0x88);return 0;}return 1;}
static void hw_account(unsigned node){unsigned b=hw_base(node),i=node==9?0:1,j,now[5];if(!hw_wait(node))return;
 now[0]=rd(b+0x44);now[1]=rd(b+0x48);now[2]=rd(b+0x4c);now[3]=rd(b+0x50);now[4]=rd(b+0x5c);
 for(j=0;j<3;j++){unsigned d=now[j]-hw_last[i][j];generated+=d;generated_by_type[j==0?1:j==1?7:5]+=d;if(j==2)load_generated+=d;}
 queue_drops+=now[3]-hw_last[i][3];retry_drops+=now[4]-hw_last[i][4];loss_expired+=now[4]-hw_last[i][4];
 memcpy(hw_last[i],now,sizeof(now));
}
static void hw_init(void){unsigned i;memset(hw_last,0,sizeof(hw_last));memset(hw_altitude_seen,0,sizeof(hw_altitude_seen));
 for(i=0;i<2;i++){unsigned b=i?0x800:0x400;wr(b,1);wr(b+4,run_id);wr(b+0x18,hw_enabled[i]);wr(b+0x1c,load_pps);if(!hw_wait(i?13:9))return;}
}
static void hw_tick(unsigned node,unsigned round){unsigned b=hw_base(node),i=node==9?0:1;Vec3 v=scene_position(node,round*.1,master_seed);if(!hw_wait(node))return;
 wr(b+8,round);wr(b+12,(unsigned)(int32_t)llround(v.x*1000));wr(b+16,(unsigned)(int32_t)llround(v.y*1000));wr(b+20,(unsigned)(int32_t)llround(v.z*1000));
 wr(b+24,hw_enabled[i]&&!node_off(node,round*.1));wr(b+28,load_pps);wr(b,2);hw_account(node);
}
static int hw_choose(unsigned node,int retry_only){unsigned b=hw_base(node);if(!hw_wait(node))return 0;if(rd(b+0x40)&4)return 1;
 /* Occupancy is maintained by the endpoint itself. An empty queue cannot
  * contain an eligible packet, so avoid a 128-entry hardware scan. Tick/RX
  * completes before this read; nonempty queues retain the exact PL scheduler. */
 if(!rd(b+0xa0))return 0;
 wr(b,retry_only?6:3);if(!hw_wait(node))return 0;hw_account(node);return (rd(b+0x40)&4)!=0;}
static void hw_peek(unsigned node,uint8_t*b){unsigned a=hw_base(node),i;for(i=0;i<96;i+=4)w32(b+i,rd(a+0x100+i));b[30]=rd(a+0x7c);}
static int hw_received_command(unsigned node,uint8_t*b,uint64_t now){unsigned base=hw_base(node),i,slot=node==9?0:1,accepted,alt_gen;if(!hw_wait(node))return 0;
 accepted=rd(base+0x84);if(!accepted||rd(base+0x8c)!=get_le32(b+32))return 0;
 if(accepted==1){for(i=0;i<command_count;i++)if(commands[i].id==get_le32(b+32)&&commands[i].target==node)commands[i].executions++;
  alt_gen=rd(base+0x90);if(alt_gen!=hw_altitude_seen[slot]){if(!scene_altitude(node,rd(base+0x74),round_index*.1,master_seed)){running=0;fatal_code=221;return 0;}hw_altitude_seen[slot]=alt_gen;}
 }
 hw_account(node);return accepted;
}
