import os
print('TG_SESSION:', os.getenv('TG_SESSION'))
print('All TG_* variables:')
for key, value in os.environ.items():
    if key.startswith('TG_'):
        print(f'  {key}: {value}') 