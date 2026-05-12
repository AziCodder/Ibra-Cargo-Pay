import { message } from 'antd';
import type { RcFile } from 'antd/es/upload';

const MAX_FILE_SIZE = 10 * 1024 * 1024;        // 10 МБ (общий)
const MAX_PAYMENT_FILE_SIZE = 3 * 1024 * 1024; // 3 МБ (для файлов платежей)

/** Валидация файла перед загрузкой. Возвращает false чтобы отменить auto-upload. */
export function validateFileBeforeUpload(file: RcFile): false {
  if (file.size > MAX_FILE_SIZE) {
    message.error(`Файл "${file.name}" превышает 10 МБ`);
    return false;
  }
  return false; // Всегда manual upload
}

/** Проверяет размер файла (общий лимит 10 МБ), возвращает true если допустим */
export function isFileSizeValid(file: File | RcFile): boolean {
  if (file.size > MAX_FILE_SIZE) {
    message.error(`Файл "${file.name}" превышает 10 МБ`);
    return false;
  }
  return true;
}

/** Проверяет размер файла платежа (лимит 3 МБ), возвращает true если допустим */
export function isPaymentFileSizeValid(file: File | RcFile): boolean {
  if (file.size > MAX_PAYMENT_FILE_SIZE) {
    message.error(`Файл "${file.name}" превышает 3 МБ`);
    return false;
  }
  return true;
}
