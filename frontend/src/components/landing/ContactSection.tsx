import { Github, Linkedin, Mail } from 'lucide-react';

const contactLinks = [
  {
    icon: Github,
    label: 'GitHub',
    href: 'https://github.com/yourusername',
  },
  {
    icon: Linkedin,
    label: 'LinkedIn',
    href: 'https://linkedin.com/in/yourusername',
  },
  {
    icon: Mail,
    label: 'Email',
    href: 'mailto:your.email@gmail.com',
  },
];

export const ContactSection: React.FC = () => {
  return (
    <section className="py-12 sm:py-16 bg-surface-secondary">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="text-center">
          <h2 className="text-xl sm:text-2xl lg:text-3xl font-bold text-text-primary mb-3 sm:mb-4">
            Get in Touch
          </h2>
          <p className="text-sm sm:text-base text-text-secondary mb-6 sm:mb-8 max-w-md mx-auto px-2">
            Have questions or feedback? Feel free to reach out!
          </p>

          <div className="flex items-center justify-center gap-4 sm:gap-6">
            {contactLinks.map((link) => {
              const Icon = link.icon;
              return (
                <a
                  key={link.label}
                  href={link.href}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="group flex flex-col items-center gap-1.5 sm:gap-2 p-3 sm:p-4 rounded-xl hover:bg-surface-tertiary transition-all duration-200"
                  aria-label={link.label}
                >
                  <div className="p-2.5 sm:p-3 bg-surface rounded-full border border-border group-hover:border-accent group-hover:bg-accent-muted transition-all duration-200">
                    <Icon className="w-5 h-5 sm:w-6 sm:h-6 text-text-secondary group-hover:text-accent transition-colors" />
                  </div>
                  <span className="text-xs sm:text-sm text-text-muted group-hover:text-text-primary transition-colors">
                    {link.label}
                  </span>
                </a>
              );
            })}
          </div>
        </div>
      </div>
    </section>
  );
};
