"""Source priority-one effects, Sonic, shadow, rings and timer composition."""
import struct
from special_contact_reference import ContactReference
from special_effect_reference import EffectReference,FIELDS,O

def empty():return {name:0 for name in FIELDS}
def clone(value):return {k:list(v) if isinstance(v,list) else v for k,v in value.items()}
class EffectLoopReference:
    def __init__(self):
        self.contacts=ContactReference();self.effects=EffectReference(self.contacts.r);self.reset()
    def reset(self):
        self.context={'seed':0,'d1':0,'ring_direction':0};self.previous_held=0
        self.dust=[empty() for _ in range(8)];self.rings=[empty() for _ in range(7)];self.drawn=[empty() for _ in range(16)];self.sats=[b'']*16
    def actor(self,e,w,held=0,sonic_y=344<<16):
        visual=empty();sat=b''
        if e['id']:
            visual,_,sat,_,_=self.effects.run(e,self.context,held,sonic_y=sonic_y,operation='actor',sounds=w['sound'])
        out,self.context,_,sounds,_=self.effects.run(e,self.context,held,sonic_y=sonic_y,sounds=w['sound']);w['sound']=sounds
        return out,visual,sat
    def step(self,p,s,w,parts,held=0,tapped=0):
        c=self.contacts;r=c.r;w=clone(w)
        if w['splash_id']:
            c.run('splash_actor',p,s,w,parts);obj=r.read(r.prg,0x33000,128)
            self.drawn[0]={name:struct.unpack_from('>'+fmt,obj,O[field])[0] for name,(field,fmt) in FIELDS.items()}
            count=r.read(r.prg,0x6024,1)[0];self.sats[0]=r.read(r.prg,0x36000,count*8)
        else:self.drawn[0]=empty();self.sats[0]=b''
        p,s,w=c.run('splash',p,s,w,parts)
        for i in range(8):
            self.dust[i]['id']=w['dust'][i]>>8;self.dust[i]['routine']=w['dust'][i]&255
            self.dust[i],self.drawn[i+1],self.sats[i+1]=self.actor(self.dust[i],w,self.previous_held)
            w['dust'][i]=(self.dust[i]['id']<<8)|self.dust[i]['routine']
        p,s,w=c.run('step',p,s,w,parts,held,tapped)
        # Execute the original intervening shadow, preserving its D1 result.
        self.context['d1']=self.effects.shadow_d1(r.lib.s68k_get_reg(1)&0xffffffff)
        for i in range(7):
            self.rings[i]['id']=w['lost_rings'][i]
            self.rings[i],self.drawn[i+9],self.sats[i+9]=self.actor(self.rings[i],w,sonic_y=p['sprite_y'])
            w['lost_rings'][i]=self.rings[i]['id']
        p,s,w=c.run('timer',p,s,w,parts);self.previous_held=held
        return p,s,w
    def hash(self):
        values=[self.context['seed'],self.context['ring_direction'],self.previous_held]
        for e in self.dust+self.rings+self.drawn:values.extend(e[name] for name in FIELDS)
        h=2166136261
        for value in values:
            for byte in value.to_bytes(4,'big'):h=((h^byte)*16777619)&0xffffffff
        return h
