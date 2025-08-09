"use client";

import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

interface MarkdownMessageProps {
  content: string;
  className?: string;
}

export function MarkdownMessage({ content, className = "" }: MarkdownMessageProps) {
  return (
    <div className={`prose prose-sm max-w-none ${className}`}>
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          h1: ({ children }) => <h1 className="text-xl font-bold mb-2 text-current">{children}</h1>,
          h2: ({ children }) => <h2 className="text-lg font-semibold mb-2 text-current">{children}</h2>,
          h3: ({ children }) => <h3 className="text-base font-semibold mb-1 text-current">{children}</h3>,
          p: ({ children }) => <p className="mb-2 last:mb-0 text-current">{children}</p>,
          ul: ({ children }) => <ul className="list-disc list-inside mb-2 space-y-1">{children}</ul>,
          ol: ({ children }) => <ol className="list-decimal list-inside mb-2 space-y-1">{children}</ol>,
          li: ({ children }) => <li className="ml-2 text-current">{children}</li>,
          code: ({ children, className, ...rest }) => {
            const isInline = !className;
            return isInline ? (
              <code className="bg-gray-100 dark:bg-gray-800 px-1 py-0.5 rounded text-sm font-mono text-current" {...rest}>
                {children}
              </code>
            ) : (
              <pre className="bg-gray-100 dark:bg-gray-800 p-3 rounded-lg text-sm font-mono overflow-x-auto mb-2">
                <code className="text-current" {...rest}>
                  {children}
                </code>
              </pre>
            );
          },
          blockquote: ({ children }) => (
            <blockquote className="border-l-4 border-gray-300 dark:border-gray-600 pl-4 italic mb-2 text-current">
              {children}
            </blockquote>
          ),
          strong: ({ children }) => <strong className="font-semibold text-current">{children}</strong>,
          em: ({ children }) => <em className="italic text-current">{children}</em>,
          a: ({ children, href }) => (
            <a 
              href={href} 
              target="_blank" 
              rel="noopener noreferrer"
              className="text-blue-600 dark:text-blue-400 hover:underline"
            >
              {children}
            </a>
          ),
        }}
      >
        {content}
      </ReactMarkdown>
    </div>
  );
}