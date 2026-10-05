/** 底部居中的轻提示，4 秒后由容器清除。 */

interface Props {
  message: string;
  isError: boolean;
}

export default function Toast({ message, isError }: Props) {
  return (
    <div
      className={`fixed left-1/2 bottom-6 -translate-x-1/2 z-50 px-4 py-2 rounded-lg text-sm shadow-lg max-w-[70vw] ${
        isError ? 'bg-red-600 text-white' : 'bg-gray-800 text-white'
      }`}
    >
      {message}
    </div>
  );
}
