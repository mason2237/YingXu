// Display state shared by either data adapter; paths remain plain text.
export const stateOf = row => row.state === '已跳过' ? '已跳过' : row.warnings.length ? '存在冲突' : row.state;
