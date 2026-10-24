"""Focus the game iframe so CDP key events reach the game (dev tool)."""
import cdp
p = cdp.Session(cdp.pick('page'))
p.call('Runtime.evaluate', expression="(()=>{const f=document.querySelector('iframe'); f.focus(); const c=f.contentDocument.querySelector('canvas'); if(c){c.tabIndex=0;c.focus();}})()")
