import { MACHINES, STREETS, SUBTYPE_ORDER } from './data.js';
import { rbRoutesByVehicle, pinnedRouteIndexByVehicle, selectedForShow } from './state.js';
import { getMachineOverrides } from './machine-actions.js';

// Raw project sources are embedded at build time, so the export also works offline.
const sources = import.meta.glob([
  '../index.html', '../package.json', '../vite.config.js', '../playwright.config.js',
  '../src/*.js', '../tests/**/*.js', '../scripts/**/*.{js,mjs,cjs}',
  '../server.cjs', '../bot.js', '../.eslintrc.json'
], { query: '?raw', import: 'default', eager: true });

export function exportAIContext() {
  const state = {
    exportedAt: new Date().toISOString(),
    machines: MACHINES.map(m => ({ ...m })),
    streets: STREETS.map(({ _layer, ...street }) => street),
    subtypeOrder: SUBTYPE_ORDER,
    routes: rbRoutesByVehicle,
    pinnedRouteIndexByVehicle,
    selectedForShow: [...selectedForShow],
    machineOverrides: getMachineOverrides(),
    browserStorage: {
      zhilischnik_v45: localStorage.getItem('zhilischnik_v45'),
      zhilischnik_v45_streets: localStorage.getItem('zhilischnik_v45_streets')
    }
  };
  const intro = `# Карта техники — контекст для продолжения работы с ИИ

Это один текстовый файл с исходниками приложения, тестами и фактическим состоянием браузера на момент выгрузки. Передайте его другому ИИ и попросите продолжить работу по нужной задаче. Исходники следует восстанавливать по разделам «Файл», сохраняя относительные пути. Не размещайте выгрузку публично: в ней могут быть пользовательские данные и фотографии data: URL.

Стек: Vite, JavaScript ES modules, Leaflet, Leaflet-Geoman; тесты Vitest и Playwright. Команды: npm install, npm run dev, npm run build, npm test, npx playwright test. Данные редактирования сохраняются в localStorage. Закреплённый маршрут у каждой машины задаётся в карточке, состояние pinnedRouteIndexByVehicle. Категории ОДХ/Дворы и участки 1–6 фильтруют карту. Вся техника — полный реестр; назначение участка возможно после выбора его номера. Экспорт — документация и снимок, а не исполняемый HTML или архив зависимостей.

Пожелания пользователя: убрать подсказку рисования у курсора; показывать закреплённые маршруты при наведении и выборе ОДХ/Дворы/Вся техника; участки 1–6 подсвечивают только свою геометрию, повторный щелчок снимает выбор (особенно проверить участок 5); показывать все машины у общего полигона/маршрута; устранить наложение значков фото и действий; дата и время сверху; добавление и удаление машин в категориях, подтипах и участках; не терять список из-за фильтров. Подробности реализации и тестов находятся ниже. При вопросах о новых правках проверяйте фактический код, а не полагайтесь только на это описание.

## Состояние браузера

\`\`\`json
${JSON.stringify(state, null, 2)}
\`\`\`
`;
  const body = Object.entries(sources).sort(([a], [b]) => a.localeCompare(b)).map(([path, text]) => {
    const name = path.replace(/^\.\.\//, '');
    return `\n## Файл: ${name}\n\n\`\`\`text\n${text}\n\`\`\`\n`;
  }).join('');
  const template = window.__SINGLE_FILE_TEMPLATE__ || '';
  const templateSection = template ? '\n## Файл: dist/index.html (собранное однофайловое приложение)\n\n```text\n' + template + '\n```\n' : '';
  const blob = new Blob([intro, body, templateSection], { type: 'text/markdown;charset=utf-8' });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = 'karta-tehniki-ai-context-' + new Date().toISOString().slice(0, 10) + '.md';
  document.body.appendChild(link);
  link.click();
  setTimeout(() => { link.remove(); URL.revokeObjectURL(url); }, 1000);
}