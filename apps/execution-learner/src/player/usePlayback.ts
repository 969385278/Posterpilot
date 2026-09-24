import {useCallback, useEffect, useRef, useState} from 'react';
import type {CallbackListener, PlayerRef} from '@remotion/player';
import {crossedStop, DURATION, nextIndex, nextStop, position, previousFrame, shouldIgnoreShortcut, startFrame, stopFrame} from '../timeline';
export function usePlayback() {
  const player = useRef<PlayerRef>(null);
  const frameRef = useRef(0);
  const target = useRef<number | null>(null);
  const running = useRef(false);
  const [frame,setFrame] = useState(0);
  const [playing,setPlaying] = useState(false);
  const [mode,setModeState] = useState<'learn'|'continuous'>('learn');
  const modeRef = useRef(mode);
  const [speed,setSpeed] = useState(1);
  const [comparison,setComparison] = useState<{frame:number; index:number}|null>(null);
  const branchRef = useRef(false);
  const sync = useCallback((f:number) => {frameRef.current=f; setFrame(f);},[]);
  const pause = useCallback(() => {running.current=false; target.current=null; player.current?.pause();setPlaying(false);},[]);
  const seek = useCallback((f:number) => {
    pause(); const safe=Math.max(0,Math.min(DURATION-1,Math.round(f)));
    sync(safe); player.current?.seekTo(safe);
  },[pause,sync]);
  useEffect(() => {
    const p=player.current; if(!p) return;
    const update:CallbackListener<'frameupdate'> = e => {
      const f=e.detail.frame;
      if(running.current && crossedStop(f,target.current)) {
        const stop=target.current!;
        pause(); sync(stop); p.seekTo(stop); return;
      }
      sync(f);
    };
    const ended:CallbackListener<'ended'> = () => {pause();sync(p.getCurrentFrame());};
    p.addEventListener('frameupdate',update);p.addEventListener('ended',ended);
    return () => {p.removeEventListener('frameupdate',update);p.removeEventListener('ended',ended);};
  },[pause,sync]);
  const run = useCallback((start:number, stop:number|null) => {
    if(branchRef.current) return;
    seek(start);target.current=stop;running.current=true;setPlaying(true);player.current?.play();
  },[seek]);
  const next = useCallback(() => {const i=nextIndex(frameRef.current);run(startFrame(i),stopFrame(i));},[run]);
  const previous = useCallback(() => seek(previousFrame(frameRef.current)),[seek]);
  const replay = useCallback(() => {const i=Math.max(0,position(frameRef.current).index);run(startFrame(i),stopFrame(i));},[run]);
  const toggle = useCallback(() => {
    if(branchRef.current) return;
    if(running.current) {pause();return;}
    const f=frameRef.current;
    if(f>=DURATION-1) {seek(0);return;}
    run(f,modeRef.current==='learn'?nextStop(f):null);
  },[pause,run,seek]);
  const setMode = useCallback((m:'learn'|'continuous') => {
    modeRef.current=m;setModeState(m);
    if(running.current) target.current=m==='learn'?nextStop(frameRef.current):null;
  },[]);
  const enterComparison = useCallback(() => {pause();branchRef.current=true;setComparison({frame:frameRef.current,index:position(frameRef.current).index});},[pause]);
  const exitComparison = useCallback(() => {if(!comparison)return; branchRef.current=false;seek(comparison.frame);setComparison(null);},[comparison,seek]);
  useEffect(() => {
    const handler=(event:KeyboardEvent) => {
      if(branchRef.current || event.altKey || event.ctrlKey || event.metaKey || shouldIgnoreShortcut(event.target,window.getSelection()?.toString()??''))return;
      if(event.code==='Space'){event.preventDefault();toggle();}
      if(event.code==='ArrowRight'){event.preventDefault();next();}
      if(event.code==='ArrowLeft'){event.preventDefault();previous();}
      if(event.code==='KeyR'){event.preventDefault();replay();}
    };
    window.addEventListener('keydown',handler);return()=>window.removeEventListener('keydown',handler);
  },[toggle,next,previous,replay]);
  return {player,frame,playing,mode,setMode,speed,setSpeed,pause,seek,next,previous,replay,toggle,comparison,enterComparison,exitComparison};
}
