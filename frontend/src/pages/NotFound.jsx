/** 404 Not Found page */
import { Link } from 'react-router-dom';

export default function NotFound() {
  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50">
      <div className="text-center">
        <p className="text-7xl font-black text-blue-700 mb-4">404</p>
        <p className="text-xl font-semibold text-gray-700 mb-2">Page not found</p>
        <p className="text-gray-500 mb-6">The page you're looking for doesn't exist.</p>
        <Link to="/" className="inline-block bg-blue-700 text-white px-5 py-2.5 rounded-lg text-sm font-medium hover:bg-blue-800 transition-colors">
          Go to home
        </Link>
      </div>
    </div>
  );
}
