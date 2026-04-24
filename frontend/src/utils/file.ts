import { message } from 'antd';
import type { RcFile } from 'antd/es/upload';

const MAX_FILE_SIZE = 10 * 1024 * 1024; // 10 МБ

/** Валидация файла перед загрузкой. Возвращает false чтобы отменить auto-upload. */
export function validateFileBeforeUpload(file: RcFile): false {
  if (file.size > MAX_FILE_SIZE) {
    message.error(`Файл "${file.name}" превышает 10 МБ`);
    // Не добавляем в fileList, возвращая Upload.LIST_IGNORE
    return false;
  }
  return false; // Всегда manual upload
}

/** Проверяет разм��р файла, возвращает true если допустим */
export function isFileSizeValid(file: File | RcFile): boolean {
  if (file.size > MAX_FILE_SIZE) {
    message.error(`Файл "${file.name}" превышает 10 МБ`);
    return false;
  }
  return true;
}
