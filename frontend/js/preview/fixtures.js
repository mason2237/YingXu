// Explicit stage 6 fixtures. These paths are display text, never disk targets.
export const ROOT = 'D:\\影库\\山海之间\\第一季';
const clone = value => structuredClone(value);
const videoName = i => `山海之间.S01E${String(i).padStart(2, '0')}.2160p.WEB-DL.H265.${i % 3 === 0 ? 'mp4' : 'mkv'}`;
function subtitle(i, lang = 'chs', score = .96) {
  const ep = String(i).padStart(2, '0');
  const target = videoName(i).replace(/\.(mkv|mp4)$/, `.${lang}.srt`);
  return {subtitleId: `sub-${i}-${lang}`, name: `山海之间.第${ep}集.字幕组.${lang}.srt`,
    displayPath: `${ROOT}\\字幕\\山海之间.第${ep}集.字幕组.${lang}.srt`,
    language: lang === 'eng' ? '英语' : '简体中文', score, manual: false, confirmed: false,
    targetName: target, targetPath: `${ROOT}\\字幕\\${target}`};
}
export function makeRow(i) {
  const name = videoName(i);
  const row = {rowId: `video-${i}`, video: {fileId: `file-${i}`, name, displayPath: `${ROOT}\\${name}`, extension: i % 3 === 0 ? '.mp4' : '.mkv'},
    subtitles: [subtitle(i, 'chs', .98 - (i % 5) * .025)], warnings: [], state: '待整理', episode: `S01E${String(i).padStart(2, '0')}`,
    basis: ['集数标识一致', '文件名称相近', '字幕位于同一剧集目录']};
  if (i === 2 || i === 9) row.subtitles.push(subtitle(i, 'eng', .94));
  if (i === 3) {row.subtitles[0].score = .68; row.state = '需确认'; row.basis = ['集数一致 · S01E03', '存在两份同语言候选', '名称差异较大，建议人工核对'];}
  if (i === 4 || i === 11) {row.subtitles = []; row.state = '未匹配'; row.basis = ['没有达到自动匹配条件的字幕'];}
  if (i === 6) {row.subtitles[0].name = row.subtitles[0].targetName; row.subtitles[0].displayPath = row.subtitles[0].targetPath; row.state = '已符合';}
  if (i === 7) row.warnings = [{code: 'TARGET_EXISTS', message: '预览目标已被占用，需要重新检查。'}];
  if (i === 12) row.state = '已跳过';
  if (i === 8) {
    row.video.name = '山海之间.S01E08.第一季.导演特别剪辑版.超长中文文件名与发行信息.2160p.WEB-DL.HEVC.10bit.HDR.mkv';
    row.video.displayPath = `${ROOT}\\${row.video.name}`;
    row.subtitles[0].targetName = row.video.name.replace('.mkv', '.chs.srt');
    row.subtitles[0].targetPath = `${ROOT}\\字幕\\${row.subtitles[0].targetName}`;
  }
  return row;
}
export function candidatesFor(row) {
  const number = Number(row.rowId.split('-').at(-1));
  const alternatives = [
    {...subtitle(number, 'chs', .82), subtitleId: `candidate-${number}-A`, name: `山海之间.S01E${String(number).padStart(2, '0')}.官方字幕.chs.srt`, reason: '集数一致，名称更接近', episode: row.episode},
    {...subtitle(number, 'chs', .64), subtitleId: `candidate-${number}-B`, name: `山海之间.第${number}集.另一版本.chs.srt`, reason: '集数一致，需核对片源版本', episode: row.episode},
    {...subtitle(number + 1, 'chs', .12), subtitleId: `candidate-${number}-C`, reason: '集数不同，存在明显冲突', episode: `S01E${String(number + 1).padStart(2, '0')}`, conflict: true},
  ];
  return clone(alternatives.map(candidate => ({...candidate,
    displayPath: `${ROOT}\\字幕\\${candidate.name}`,
    targetName: row.video.name.replace(/\.(mkv|mp4)$/, '.chs.srt'),
    targetPath: `${ROOT}\\字幕\\${row.video.name.replace(/\.(mkv|mp4)$/, '.chs.srt')}`,
  })));
}
export const historyFixture = [{recordId: 'history-sample', title: '山海之间 · 第一季', time: '示例记录 · 2026/10/20 20:16', success: 18, skipped: 2, errors: 1,
  items: [{source: '山海之间.第01集.chs.srt', target: '山海之间.S01E01.chs.srt', state: '成功'},
    {source: '山海之间.第02集.eng.srt', target: '山海之间.S01E02.eng.srt', state: '成功'},
    {source: '山海之间.第03集.chs.srt', target: '山海之间.S01E03.chs.srt', state: '权限不足'}]}];
