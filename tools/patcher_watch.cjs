'use strict';
// Independent timer for asynchronous Chrome tests; closes only their browser.
const fs=require('node:fs'),path=require('node:path');
module.exports=function watch(root,stop){
 const device=fs.statSync(root).dev,schedule=JSON.parse(fs.readFileSync(path.join(root,'QA-SCHEDULE.json'),'utf8'));
 function reason(){
  try{
   const disk=fs.statfsSync(root,{bigint:true});
   if(fs.statSync(root).dev!==device)return 'workspace mount changed';
   if(disk.bavail*disk.bsize<100n*1024n**3n)return 'Disk reserve below 100 GiB';
  }catch{return 'workspace mount lost';}
  const fields=Object.fromEntries(new Intl.DateTimeFormat('en-US',{timeZone:schedule.timezone,weekday:'short',hour:'2-digit',minute:'2-digit',hourCycle:'h23'}).formatToParts(new Date()).map(p=>[p.type,p.value]));
  const day=['Mon','Tue','Wed','Thu','Fri','Sat','Sun'].indexOf(fields.weekday),minute=Number(fields.hour)*60+Number(fields.minute);
  if(schedule.blocked_weekdays.includes(day)&&minute>=schedule.blocked_start_hour*60-schedule.job_stop_lead_minutes&&minute<schedule.blocked_end_hour*60)return 'scheduled shutdown window';
  return null;
 }
 const initial=reason();if(initial)throw Error(initial);
 const timer=setInterval(()=>{const cause=reason();if(cause){clearInterval(timer);stop(cause);}},1000);
 return ()=>clearInterval(timer);
};
