/* Illustrates the documented bulk preview → approval → execute flow. No Tower, agent or network calls. */
(() => {
  const root = document.querySelector('[data-fleet-flow]');
  if (!root) return;
  const media = matchMedia('(prefers-reduced-motion: reduce)');
  const stages = [...root.querySelectorAll('[data-fleet-stage]')];
  const map = root.querySelector('.fleet-map');
  const names = ['Preview', 'Frozen targets', 'Approval', 'Execute'];
  let phase = media.matches ? 3 : 0;
  let approver = 'alice';
  let playing = !media.matches;
  let visible = false;
  let timer;
  const set = (selector, text) => { root.querySelector(selector).textContent = text; };
  const svgNS = 'http://www.w3.org/2000/svg';
  const svg = document.createElementNS(svgNS, 'svg');
  svg.setAttribute('aria-hidden', 'true');
  svg.classList.add('fleet-wires');
  map.prepend(svg);
  const wires = stages.slice(1).map(() => {
    const group = document.createElementNS(svgNS, 'g');
    for (const cls of ['fleet-wire-track', 'fleet-wire-pulse']) {
      const path = document.createElementNS(svgNS, 'path');
      path.classList.add(cls); group.append(path);
    }
    svg.append(group); return group;
  });
  function drawWires() {
    const bounds = map.getBoundingClientRect();
    if (!bounds.width || !bounds.height) return;
    svg.setAttribute('viewBox', `0 0 ${bounds.width} ${bounds.height}`);
    wires.forEach((group, i) => {
      const from = stages[i].getBoundingClientRect();
      const to = stages[i + 1].getBoundingClientRect();
      const down = to.top > from.top + 10;
      const x1 = (down ? from.left + from.width / 2 : from.right) - bounds.left;
      const y1 = (down ? from.bottom : from.top + from.height / 2) - bounds.top;
      const x2 = (down ? to.left + to.width / 2 : to.left) - bounds.left;
      const y2 = (down ? to.top : to.top + to.height / 2) - bounds.top;
      const d = down
        ? `M ${x1} ${y1} C ${x1} ${(y1+y2)/2}, ${x2} ${(y1+y2)/2}, ${x2} ${y2}`
        : `M ${x1} ${y1} C ${(x1+x2)/2} ${y1}, ${(x1+x2)/2} ${y2}, ${x2} ${y2}`;
      [...group.children].forEach(path => path.setAttribute('d', d));
      group.style.setProperty('--fleet-wire-length', group.firstChild.getTotalLength());
    });
  }
  function render(manual = false) {
    const self = approver === 'alice';
    const decided = phase >= 2;
    const done = phase === 3;
    root.dataset.approver = approver;
    root.dataset.phase = String(phase);
    root.dataset.outcome = decided ? (self ? 'rejected' : 'approved') : 'pending';
    set('[data-fleet-verdict]', decided ? (self ? 'REJECTED' : 'APPROVED') : 'Awaiting review');
    set('[data-fleet-reason]', decided
      ? (self ? 'Alice proposed this change, so she cannot approve it.' : 'Bob is a different operator, so approval is accepted.')
      : 'No one has signed off on the frozen list yet.');
    set('[data-fleet-signer]', decided ? `By: ${approver}` : 'By: —');
    set('[data-fleet-exec-title]', done ? (self ? 'Nothing changed' : '3 agents updated') : 'Change held');
    set('[data-fleet-exec-code]', done ? (self ? 'execute refused' : 'enhanced_tracing = true') : 'not executed');
    set('[data-fleet-exec-detail]', done
      ? (self ? 'Without a valid approval, execute is refused for every target.' : 'checkout, refund and triage succeed. Each result is written to the audit trail.')
      : 'Nothing runs before a different operator approves.');
    set('[data-fleet-exec-count]', done && !self ? '3 succeeded' : '0 changed');
    const statuses = [
      'PREVIEW SAVED',
      'LIST LOCKED',
      self ? 'SELF-APPROVAL DENIED' : 'SECOND PERSON SIGNED',
      self ? 'NOT EXECUTED' : 'AUDIT RECORDED'
    ];
    stages.forEach((node, i) => {
      const completed = i < phase || (done && i === 3);
      node.classList.toggle('active', i === phase);
      node.classList.toggle('complete', completed);
      const check = node.querySelector('.fleet-check');
      check.textContent = completed ? '✓' : '·';
      check.setAttribute('aria-label', completed ? 'Complete' : i === phase ? 'Checking' : 'Pending');
      set(`[data-fleet-stage-status="${i}"]`, completed ? statuses[i] : i === phase ? 'IN PROGRESS' : 'WAITING');
    });
    wires.forEach((group, i) => {
      group.setAttribute('class', phase === i + 1 ? 'pinging' : phase > i + 1 ? 'done' : 'pending');
    });
    const stories = [
      ['Alice proposes one change for staging.', 'The selector staging + agenticlens matches checkout, refund and triage. checkout-agent-prod is in production, so it is never selected.'],
      ['The list is frozen at preview.', 'search-agent registers a moment later. It is not added, because approval will only ever cover the list that was reviewed.'],
      self ? ['Alice cannot approve her own change.'] : ['Bob approves the frozen list.'],
      self ? ['Nothing moves without a second person.'] : ['Three agents changed. Production untouched.']
    ];
    stories[2].push(self
      ? 'Even with an approver role, bulk.decide raises "Approval requires a different operator".'
      : 'Approval covers exactly the three agents in the preview, before and after settings included.');
    stories[3].push(self
      ? 'The batch stays pending, so execute is refused and no agent setting changes.'
      : 'Each target reports succeeded. The audit trail names Alice as proposer and executor and Bob as approver.');
    root.querySelector('.fleet-result').setAttribute('aria-live', manual ? 'polite' : 'off');
    set('[data-fleet-phase]', `${String(phase + 1).padStart(2,'0')} / ${names[phase].toUpperCase()}`);
    set('[data-fleet-result]', stories[phase][0]);
    set('[data-fleet-detail]', stories[phase][1]);
    set('[data-fleet-changed]', done && !self ? '3' : '0');
    set('[data-fleet-playback]', `${playing ? 'Automatic playback' : media.matches ? 'Static overview · reduced motion' : 'Paused'} · approver: ${approver}`);
    set('[data-fleet-play]', playing ? 'Ⅱ Pause animation' : '▶ Play animation');
    root.querySelector('[data-fleet-play]').setAttribute('aria-pressed', String(playing));
    root.querySelector('.fleet-progress>span').style.width = ((phase + 1) / 4 * 100) + '%';
    schedule();
  }
  function schedule() {
    clearTimeout(timer);
    const running = playing && visible && !document.hidden;
    root.classList.toggle('fleet-playing', running);
    if (running) timer = setTimeout(() => {
      if (!visible || document.hidden) { schedule(); return; }
      if (phase === 3) { phase = 0; approver = approver === 'alice' ? 'bob' : 'alice'; }
      else phase++;
      render();
    }, phase === 3 ? 2800 : 1300);
  }
  root.querySelectorAll('button').forEach(button => { button.hidden = false; });
  root.addEventListener('click', event => {
    const button = event.target.closest('button'); if (!button) return;
    if (button.hasAttribute('data-fleet-play')) playing = !playing;
    else if (button.hasAttribute('data-fleet-replay')) { approver = 'alice'; phase = 0; playing = true; }
    else return;
    render(true);
  });
  new ResizeObserver(drawWires).observe(map);
  document.fonts.ready.then(drawWires);
  new IntersectionObserver(entries => { visible = entries[0].isIntersecting; schedule(); }, { threshold: 0.12 }).observe(root);
  document.addEventListener('visibilitychange', schedule);
  media.addEventListener('change', () => {
    if (media.matches) { playing = false; approver = 'alice'; phase = 3; }
    render();
  });
  render(); drawWires();
})();
