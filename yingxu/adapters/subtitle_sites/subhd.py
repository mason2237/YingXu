"""SubHD's observed search controls; navigation stays with the site's handler."""
import json

from .websites import SUBHD_HOSTS


def submit_search_script(query, hosts=SUBHD_HOSTS):
    # Observed on the real site: no form element;
    # input#sn[name=subhd_search] and button#searchbutton drive site navigation.
    payload = json.dumps({"query": query, "hosts": sorted(hosts)}, ensure_ascii=True)
    return r"""(async () => {
      const config = PAYLOAD;
      const u = new URL(location.href);
      if (u.protocol !== 'https:' || !config.hosts.includes(u.hostname)
          || (u.port && u.port !== '443') || u.username || u.password) return {status:'untrusted'};
      const inputs = document.querySelectorAll('input#sn[name="subhd_search"][type="search"]');
      const buttons = document.querySelectorAll('button#searchbutton');
      if (inputs.length !== 1 || buttons.length !== 1) return {status:'no_control'};
      const input = inputs[0], button = buttons[0];
      // At the embedded viewport width Bootstrap collapses the search controls.
      // Use the site's observed navigation toggle, then its own search handler.
      if (!input.getClientRects().length) {
        const toggles=document.querySelectorAll('button.navbar-toggler[data-bs-target="#navbar"]');
        if (toggles.length===1 && toggles[0].getClientRects().length && !toggles[0].disabled) {
          HTMLButtonElement.prototype.click.call(toggles[0]);
          for(let attempt=0;attempt<12&&!input.getClientRects().length;attempt++)await new Promise(resolve=>setTimeout(resolve,50));
        }
      }
      if (input.disabled || button.disabled || !input.getClientRects().length
          || !button.getClientRects().length) return {status:'unavailable'};
      Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set.call(input,config.query);
      input.dispatchEvent(new Event('input',{bubbles:true}));
      input.dispatchEvent(new Event('change',{bubbles:true}));
      HTMLButtonElement.prototype.click.call(button);
      return {status:'submitted'};
    })()""".replace("PAYLOAD", payload)


def download_script(candidate_url, hosts=SUBHD_HOSTS):
    from urllib.parse import urlsplit
    identifier=urlsplit(candidate_url).path.rstrip('/').split('/')[-1]
    import re
    if not re.fullmatch(r'[A-Za-z0-9]+',identifier):return None
    payload=json.dumps({'id':identifier,'hosts':sorted(hosts)},ensure_ascii=True)
    return r"""(() => {
      const c=PAYLOAD,u=new URL(location.href);
      if(u.protocol!=='https:'||!c.hosts.includes(u.hostname)||u.username||u.password||(u.port&&u.port!=='443'))return {status:'untrusted'};
      if(!new RegExp('^/(a|down)/'+c.id+'/?$').test(u.pathname))return {status:'manual'};
      const challenge=document.querySelector('iframe[src*="challenges.cloudflare"],iframe[src*="recaptcha"],input[name="captcha"],img[src*="captcha"]');
      if(challenge&&challenge.getClientRects().length)return {status:'manual',message:'网站需要人工验证，请在右侧完成后继续。'};
      const buttons=[...document.querySelectorAll('button,a')].filter(node=>
        /^(下载字幕文件|下载字幕|下载文件|Download)$/i.test(node.textContent.trim())&&node.getClientRects().length&&!node.disabled);
      if(buttons.length!==1)return {status:'manual'};
      buttons[0].click();return {status:'clicked'};
    })()""".replace('PAYLOAD',payload)
