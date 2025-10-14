from themes import dark_theme

s = dark_theme.get_dark_stylesheet()
print('LEN:', len(s))
print('HAS data:image:', 'data:image' in s)
print('COUNT data:image:', s.count('data:image'))
# show nearby context for first occurrence
i = s.find('data:image')
if i!=-1:
    print('\n...context (first 200 chars):')
    print(s[i-40:i+160])
# search for malformed xmlns fragment
print('\nHAS truncated xmlns fragment:', 'http://www.w3.org/2000/sv' in s)
print('\nFirst 400 chars of stylesheet:\n')
print(s[:400])
