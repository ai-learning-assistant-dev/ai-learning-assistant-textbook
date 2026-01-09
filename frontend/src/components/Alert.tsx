import { AlertProps } from '../types';

export default function Alert({ message, type, onClose }: AlertProps) {
  if (!message) return null;

  const alertClasses = {
    success: 'bg-green-100 text-green-800 border-green-200',
    error: 'bg-red-100 text-red-800 border-red-200',
    warning: 'bg-yellow-100 text-yellow-800 border-yellow-200',
  };

  return (
    <div className={`p-3 rounded-lg mb-5 text-sm border ${alertClasses[type]}`}>
      {message}
    </div>
  );
}

