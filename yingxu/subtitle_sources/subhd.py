"""SubHD's observed search controls; navigation stays with the site's handler."""
import json

from .websites import SUBHD_HOSTS


def submit_search_script(query, hosts=SUBHD_HOSTS):
    # Observed in the real Qt page on 2026-10-23: no form element;
    # input#sn[name=subhd_search] and button#searchbutton drive site navigation.
    payload = json.dumps({"query": query, "hosts": sorted(hosts)}, ensure_ascii=True)
    return r"""(() => {
      const config = PAYLOAD;
      const u = new URL(location.href);
      if (u.protocol !== 'https:' || !config.hosts.includes(u.hostname)
          || (u.port && u.port !== '443') || u.username || u.password) return {status:'untrusted'};
      const inputs = document.querySelectorAll('input#sn[name="subhd_search"][type="search"]');
      const buttons = document.querySelectorAll('button#searchbutton');
      if (inputs.length !== 1 || buttons.length !== 1) return {status:'no_control'};
      const input = inputs[0], button = buttons[0];
      if (input.disabled || button.disabled || !input.getClientRects().length
          || !button.getClientRects().length) return {status:'unavailable'};
      Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set.call(input,config.query);
      input.dispatchEvent(new Event('input',{bubbles:true}));
      input.dispatchEvent(new Event('change',{bubbles:true}));
      HTMLButtonElement.prototype.click.call(button);
      return {status:'submitted'};
    })()""".replace("PAYLOAD", payload)
