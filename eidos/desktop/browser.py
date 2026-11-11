from .intents import navigation_url, search_url


class Browser:
    def __init__(self, settings, backend):
        self.settings, self.backend = settings, backend

    def open(self, action, args):
        url = ('https://www.google.com/' if action == 'browser' else
               search_url(args['query'], self.settings.search_provider) if action == 'search_browser' else args['url'])
        self.backend.launch(navigation_url(url))
        return 'Ищу: ' + args['query'] if action == 'search_browser' else 'Открываю ' + args.get('title', 'браузер')
