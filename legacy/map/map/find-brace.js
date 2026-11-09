// find-brace.js — ищет строку, где баланс скобок нарушается
import fs from 'fs';

const content = fs.readFileSync('index.html', 'utf8');
const lines = content.split('\n');

let openBraces = 0;
let closeBraces = 0;

lines.forEach((line, i) => {
  // Считаем скобки (игнорируем строки внутри комментариев //)
  const cleanLine = line.replace(/\/\/.*$/, '');
  
  const open = (cleanLine.match(/{/g) || []).length;
  const close = (cleanLine.match(/}/g) || []).length;
  
  openBraces += open;
  closeBraces += close;
  
  // Если баланс нарушился — выводим строку
  if (closeBraces > openBraces) {
    console.log(`⚠️ Лишняя } на строке ${i + 1}:`);
    console.log(`   ${line.trim()}`);
    console.log(`   Баланс: { ${openBraces}, } ${closeBraces}`);
  }
});

console.log(`\nИтог: { ${openBraces}, } ${closeBraces}`);
if (openBraces === closeBraces) {
  console.log('✅ Баланс скобок в порядке (но это не точно, т.к. скобки в строках тоже считаются)');
} else {
  console.log('❌ Есть расхождение');
}