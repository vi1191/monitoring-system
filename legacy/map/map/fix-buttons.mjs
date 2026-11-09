import fs from 'fs';
let code = fs.readFileSync('src/ui-controls.js', 'utf8');

const openAdd = `
export function openAddToCategory() {
  const modal = document.getElementById('modal-overlay');
  if (!modal) return;
  modal.classList.add('open');
  document.getElementById('modal-title').textContent = 'обавить в категорию';
  const list = document.getElementById('modal-list');
  list.innerHTML = '';
  MACHINES.forEach(m => {
    const div = document.createElement('div');
    div.className = 'copy-item';
    div.innerHTML = '<span class="plate">' + m.plate + '</span><span class="model">' + (m.model || '') + '</span><span class="cat">' + (m.cat_b || '') + '</span>';
    div.onclick = () => {
      if (typeof window.setCategory === 'function') window.setCategory('dvory');
      modal.classList.remove('open');
    };
    list.appendChild(div);
  });
}
`;
const removeFromCat = `
export function removeFromCategory() {
  const cards = document.querySelectorAll('.machine-card.selected');
  if (cards.length === 0) {
    alert('ыберите технику (галочками) для удаления');
    return;
  }
  alert('брано ' + cards.length + ' машин (демо)');
}
`;
const openPicker = `
export function openPicker() {
  const picker = document.getElementById('picker');
  if (picker) picker.classList.add('open');
}
`;
code = code.replace("export function openAddToCategory() { console.log('[TODO] openAddToCategory'); }", openAdd);
code = code.replace("export function removeFromCategory() { console.log('[TODO] removeFromCategory'); }", removeFromCat);
code = code.replace("export function openPicker() { console.log('[TODO] openPicker'); }", openPicker);
fs.writeFileSync('src/ui-controls.js', code, 'utf8');
console.log('СХ: нопки ожили!');
