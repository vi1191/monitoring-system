// Единое окно для сообщений, подтверждений и ввода.
export function showDialog(message, { title = 'Подтверждение', input = false, initialValue = '', confirmLabel = 'Продолжить', cancel = true } = {}) {
  return new Promise(resolve => {
    const overlay = document.getElementById('action-dialog');
    const panel = overlay.querySelector('.dialog-panel');
    const field = overlay.querySelector('input');
    const previousFocus = document.activeElement;
    overlay.querySelector('.dialog-title').textContent = title;
    overlay.querySelector('.dialog-message').textContent = message;
    overlay.querySelector('.dialog-ok').textContent = confirmLabel;
    overlay.querySelector('.dialog-cancel').hidden = !cancel;
    field.hidden = !input;
    field.value = initialValue;
    overlay.hidden = false;
    (input ? field : overlay.querySelector(cancel ? '.dialog-cancel' : '.dialog-ok')).focus();

    function finish(value) {
      overlay.hidden = true;
      overlay.removeEventListener('keydown', onKey);
      overlay.querySelector('.dialog-ok').removeEventListener('click', onOK);
      overlay.querySelector('.dialog-cancel').removeEventListener('click', onCancel);
      overlay.removeEventListener('click', onBackdrop);
      previousFocus?.focus?.();
      resolve(value);
    }
    function onOK() { finish(input ? field.value : true); }
    function onCancel() { finish(input ? null : false); }
    function onBackdrop(e) { if (e.target === overlay && cancel) onCancel(); }
    function onKey(e) {
      if (e.key === 'Escape' && cancel) { e.preventDefault(); e.stopPropagation(); onCancel(); }
      if (e.key === 'Enter') { e.preventDefault(); onOK(); }
      if (e.key === 'Tab') {
        const focusable = [...panel.querySelectorAll('input:not([hidden]), button:not([hidden])')];
        const i = focusable.indexOf(document.activeElement);
        if (e.shiftKey && i === 0) { e.preventDefault(); focusable.at(-1).focus(); }
        else if (!e.shiftKey && i === focusable.length - 1) { e.preventDefault(); focusable[0].focus(); }
      }
    }
    overlay.addEventListener('keydown', onKey);
    overlay.addEventListener('click', onBackdrop);
    overlay.querySelector('.dialog-ok').addEventListener('click', onOK);
    overlay.querySelector('.dialog-cancel').addEventListener('click', onCancel);
  });
}

export const notify = (message) => showDialog(message, { title: 'Внимание', confirmLabel: 'Понятно', cancel: false });
export const confirmAction = (message) => showDialog(message);
export const requestText = (message, initialValue = '') => showDialog(message, { title: 'Введите значение', input: true, initialValue, confirmLabel: 'Сохранить' });